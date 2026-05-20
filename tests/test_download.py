import os
import importlib.util
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from urllib.error import URLError

# Load 1-download.py
_root = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("download", os.path.join(_root, "1-download.py"))
download = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(download)


# ---------------------------------------------------------------------------
# download_file
# ---------------------------------------------------------------------------

class TestDownloadFile:
    def test_successful_download(self, tmp_path):
        filepath = str(tmp_path / "test.zip")
        with patch("urllib.request.urlretrieve") as mock_retrieve:
            result = download.download_file("http://example.com/test.zip", filepath)
        assert result is True
        mock_retrieve.assert_called_once_with("http://example.com/test.zip", filepath)

    def test_retries_on_url_error(self, tmp_path):
        filepath = str(tmp_path / "test.zip")
        with patch("urllib.request.urlretrieve") as mock_retrieve, \
             patch("time.sleep"):
            mock_retrieve.side_effect = [URLError("connection refused"), None]
            result = download.download_file("http://example.com/test.zip", filepath)
        assert result is True
        assert mock_retrieve.call_count == 2

    def test_returns_false_after_all_retries_exhausted(self, tmp_path):
        filepath = str(tmp_path / "test.zip")
        with patch("urllib.request.urlretrieve") as mock_retrieve, \
             patch("time.sleep"):
            mock_retrieve.side_effect = URLError("persistent error")
            result = download.download_file("http://example.com/test.zip", filepath)
        assert result is False
        assert mock_retrieve.call_count == download.RETRY_ATTEMPTS

    def test_partial_file_removed_on_url_error(self, tmp_path):
        filepath = str(tmp_path / "test.zip")
        # Simulate urlretrieve writing a partial file then raising
        def write_partial_then_fail(url, path):
            with open(path, 'wb') as f:
                f.write(b"partial content")
            raise URLError("dropped connection")
        with patch("urllib.request.urlretrieve", side_effect=write_partial_then_fail), \
             patch("time.sleep"):
            download.download_file("http://example.com/test.zip", filepath)
        assert not os.path.exists(filepath)

    def test_partial_file_removed_on_unexpected_error(self, tmp_path):
        filepath = str(tmp_path / "test.zip")
        def write_partial_then_fail(url, path):
            with open(path, 'wb') as f:
                f.write(b"partial content")
            raise RuntimeError("unexpected")
        with patch("urllib.request.urlretrieve", side_effect=write_partial_then_fail):
            download.download_file("http://example.com/test.zip", filepath)
        assert not os.path.exists(filepath)


# ---------------------------------------------------------------------------
# download_weekly_data — skip-if-exists
# ---------------------------------------------------------------------------

class TestDownloadWeeklyData:
    def test_skips_existing_files(self, tmp_path):
        # end must be >14 days past the last expected file due to RECENT_DAYS_TO_EXCLUDE
        # end - 14 days = 2024-01-22, so files 20240108 and 20240115 are both in range
        with patch.object(download, 'DOWNLOAD_DIR', str(tmp_path) + "/"):
            filename = "20240108.zip"
            (tmp_path / filename).write_bytes(b"existing")
            with patch.object(download, 'download_file') as mock_dl:
                start = date(2024, 1, 8)
                end = date(2024, 2, 5)
                download.download_weekly_data(start, end)
            called_paths = [call.args[1] for call in mock_dl.call_args_list]
            assert not any("20240108" in p for p in called_paths)
            assert any("20240115" in p for p in called_paths)

    def test_downloads_missing_files(self, tmp_path):
        # end must be >14 days past start to have any files in the eligible window
        with patch.object(download, 'DOWNLOAD_DIR', str(tmp_path) + "/"):
            with patch.object(download, 'download_file') as mock_dl:
                start = date(2024, 1, 8)
                end = date(2024, 2, 5)
                download.download_weekly_data(start, end)
            assert mock_dl.call_count >= 1


# ---------------------------------------------------------------------------
# download_yearly_data — skip-if-exists
# ---------------------------------------------------------------------------

class TestDownloadYearlyData:
    def test_skips_existing_year_file(self, tmp_path):
        with patch.object(download, 'DOWNLOAD_DIR', str(tmp_path) + "/"):
            (tmp_path / "2023.zip").write_bytes(b"existing")
            with patch.object(download, 'download_file') as mock_dl:
                download.download_yearly_data(2022, 2025)
            called_paths = [call.args[1] for call in mock_dl.call_args_list]
            assert not any("2023" in p for p in called_paths)
            assert any("2022" in p for p in called_paths)
            assert any("2024" in p for p in called_paths)

    def test_downloads_all_when_none_exist(self, tmp_path):
        with patch.object(download, 'DOWNLOAD_DIR', str(tmp_path) + "/"):
            with patch.object(download, 'download_file') as mock_dl:
                download.download_yearly_data(2022, 2025)
            assert mock_dl.call_count == 3  # 2022, 2023, 2024


# ---------------------------------------------------------------------------
# RECENT_DAYS_TO_EXCLUDE constant name
# ---------------------------------------------------------------------------

def test_constant_named_days_not_weeks():
    assert hasattr(download, 'RECENT_DAYS_TO_EXCLUDE'), \
        "Constant should be RECENT_DAYS_TO_EXCLUDE (was RECENT_WEEKS_TO_EXCLUDE)"
    assert not hasattr(download, 'RECENT_WEEKS_TO_EXCLUDE'), \
        "Old constant RECENT_WEEKS_TO_EXCLUDE should no longer exist"
