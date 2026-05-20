import os
import shutil
import zipfile
import importlib.util
import pytest
from unittest.mock import patch

# Load 3-archive.py
_root = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("archive", os.path.join(_root, "3-archive.py"))
archive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(archive)


def _run_archive(tmp_path):
    """Helper: create a CSV and run create_archive, returning the zip path."""
    csv_path = tmp_path / "extract-3-very-clean.csv"
    csv_path.write_text("col1,col2\n1,2\n")
    return archive.create_archive(
        csv_path=str(csv_path),
        output_dir=str(tmp_path / "output"),
    )


class TestCreateArchive:
    def test_raises_if_csv_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Run 2-extract.py first"):
            archive.create_archive(
                csv_path=str(tmp_path / "nonexistent.csv"),
                output_dir=str(tmp_path / "output"),
            )

    def test_creates_output_directory(self, tmp_path):
        output_dir = tmp_path / "output"
        assert not output_dir.exists()
        _run_archive(tmp_path)
        assert output_dir.exists()

    def test_creates_dated_zip_in_output_dir(self, tmp_path):
        zip_path = _run_archive(tmp_path)
        assert os.path.exists(zip_path)
        assert "output" in zip_path
        assert "nsw-property-sales-data-updated" in zip_path
        assert zip_path.endswith(".zip")

    def test_zip_contains_csv(self, tmp_path):
        zip_path = _run_archive(tmp_path)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert len(names) == 1
        assert names[0].endswith(".csv")

    def test_original_csv_preserved(self, tmp_path):
        csv_path = tmp_path / "extract-3-very-clean.csv"
        csv_path.write_text("col1,col2\n1,2\n")
        archive.create_archive(
            csv_path=str(csv_path),
            output_dir=str(tmp_path / "output"),
        )
        assert csv_path.exists()

    def test_creates_generic_archive_copy_in_output_dir(self, tmp_path):
        _run_archive(tmp_path)
        assert (tmp_path / "output" / "archive.zip").exists()

    def test_old_dated_zips_cleaned_up(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        # Plant a stale dated zip from a previous run
        stale = output_dir / "nsw-property-sales-data-updated20200101.zip"
        stale.write_bytes(b"old archive")
        _run_archive(tmp_path)
        assert not stale.exists()

    def test_only_current_dated_zip_remains(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "nsw-property-sales-data-updated20200101.zip").write_bytes(b"old")
        (output_dir / "nsw-property-sales-data-updated20210101.zip").write_bytes(b"older")
        _run_archive(tmp_path)
        dated_zips = [
            f for f in os.listdir(output_dir)
            if f.startswith("nsw-property-sales-data-updated") and f.endswith(".zip")
        ]
        assert len(dated_zips) == 1

    def test_archive_zip_not_deleted_as_old_dated_zip(self, tmp_path):
        # archive.zip must not be treated as a "dated" zip and removed
        _run_archive(tmp_path)
        assert (tmp_path / "output" / "archive.zip").exists()

    def test_uses_shutil_not_os_system(self, tmp_path):
        csv_path = tmp_path / "extract-3-very-clean.csv"
        csv_path.write_text("col1,col2\n1,2\n")
        with patch("shutil.copy2", wraps=shutil.copy2) as mock_copy, \
             patch("os.system") as mock_os_system:
            archive.create_archive(
                csv_path=str(csv_path),
                output_dir=str(tmp_path / "output"),
            )
        mock_copy.assert_called_once()
        mock_os_system.assert_not_called()
