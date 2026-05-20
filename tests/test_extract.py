import io
import os
import zipfile
import importlib.util
import pytest
import pandas as pd
from datetime import date, timedelta
from unittest.mock import patch

# Load 2-extract.py (can't use normal import due to leading digit and hyphen)
_root = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("extract", os.path.join(_root, "2-extract.py"))
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(**overrides):
    base = {
        "District code": "001",
        "Property ID": "12345",
        "Sale counter": "1",
        "Download date / time": None,
        "Property name": "test property",
        "Property unit number": None,
        "Property house number": "10",
        "Property street name": "main st",
        "Property locality": "sydney",
        "Property post code": "2000",
        "Area": "500",
        "Area type": "M",
        "Contract date": "20240115",
        "Settlement date": "20240215",
        "Purchase price": "1500000",
        "Zoning": "R2",
        "Nature of property": "RESIDENTIAL",
        "Primary purpose": "dwelling",
        "Strata lot number": None,
        "Dealing number": "DEAL001",
        "Property legal description": "LOT 1 DP 123",
    }
    base.update(overrides)
    return base


def _current_b_line(district="001", prop_id="12345", sale="1", contract="20240115",
                    price="1500000", area="500", area_type="M"):
    return (f"B;{district};{prop_id};{sale};20240101120000;NAME;1;10;"
            f"MAIN ST;SYDNEY;2000;{area};{area_type};{contract};20240215;"
            f"{price};R2;RESIDENTIAL;DWELLING;5;x;x;x;DEAL001;x")


def _archived_b_line(district="001", source="ARCHIVE", prop_id="9876",
                     contract="15/06/1995", price="350000", area="500", area_type="M"):
    return (f"B;{district};{source};extra;{prop_id};"
            f"2A;15;MAIN ST;PARRAMATTA;2150;{contract};{price};"
            f"LOT 1 DP 12345;{area};{area_type};x;x;R2")


def _make_zip_with_dat(content: str, tmp_path, inner=False) -> str:
    """Write an in-memory zip to disk and return its path."""
    zip_path = str(tmp_path / "test.zip")
    if inner:
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, 'w') as inner_zf:
            inner_zf.writestr("data.dat", content)
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("inner.zip", inner_buf.getvalue())
    else:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.dat", content)
    return zip_path


# ---------------------------------------------------------------------------
# parse_current_record
# ---------------------------------------------------------------------------

class TestParseCurrentRecord:
    def test_valid_record(self):
        parts = ["B", "001", "12345", "1", "20240101120000",
                 "NAME", "1", "10", "MAIN ST", "SYDNEY", "2000",
                 "500", "M", "20240115", "20240215", "1500000",
                 "R2", "RESIDENTIAL", "DWELLING", "5",
                 "x", "x", "x", "DEAL001", "x"]
        rec = extract.parse_current_record(parts)
        assert rec is not None
        assert rec["District code"] == "001"
        assert rec["Property ID"] == "12345"
        assert rec["Sale counter"] == "1"
        assert rec["Purchase price"] == "1500000"
        assert rec["Dealing number"] == "DEAL001"
        assert rec["Property legal description"] is None

    def test_too_short_returns_none(self):
        assert extract.parse_current_record(["B"] * 24) is None

    def test_minimum_length_accepted(self):
        parts = ["B"] + [str(i) for i in range(24)]
        assert extract.parse_current_record(parts) is not None


# ---------------------------------------------------------------------------
# parse_archived_record
# ---------------------------------------------------------------------------

class TestParseArchivedRecord:
    def test_valid_record(self):
        parts = ["B", "001", "ARCHIVE", "extra", "9876",
                 "2A", "15", "MAIN ST", "PARRAMATTA", "2150",
                 "15/06/1995", "350000", "LOT 1 DP 12345", "500", "M",
                 "x", "x", "R2"]
        rec = extract.parse_archived_record(parts)
        assert rec is not None
        assert rec["Contract date"] == "19950615"
        assert rec["Property ID"] == "9876"
        assert rec["Purchase price"] == "350000"
        assert rec["Property legal description"] == "LOT 1 DP 12345"
        assert rec["Sale counter"] is None

    def test_too_short_returns_none(self):
        assert extract.parse_archived_record(["B"] * 17) is None

    def test_invalid_date_kept_as_string(self):
        parts = ["B", "001", "ARCHIVE", "extra", "9876",
                 "2A", "15", "MAIN ST", "PARRAMATTA", "2150",
                 "BADDATE", "350000", "LOT 1 DP 12345", "500", "M",
                 "x", "x", "R2"]
        rec = extract.parse_archived_record(parts)
        assert rec is not None
        assert rec["Contract date"] == "BADDATE"


# ---------------------------------------------------------------------------
# is_archived heuristic
# ---------------------------------------------------------------------------

class TestIsArchivedHeuristic:
    def test_numeric_property_id_is_current_format(self):
        records = extract.parse_data_lines([_current_b_line(prop_id="12345")])
        assert len(records) == 1
        assert records[0]["Sale counter"] == "1"  # only current format has sale counter

    def test_alpha_source_is_archived_format(self):
        records = extract.parse_data_lines([_archived_b_line(source="ARCHIVE")])
        assert len(records) == 1
        assert records[0]["Sale counter"] is None  # archived has no sale counter

    def test_alphanumeric_source_valnet1_is_archived(self):
        # VALNET1 has a digit; old isalpha() heuristic would misclassify it as current
        records = extract.parse_data_lines([_archived_b_line(source="VALNET1")])
        assert len(records) == 1
        assert records[0]["Sale counter"] is None


# ---------------------------------------------------------------------------
# parse_data_lines
# ---------------------------------------------------------------------------

class TestParseDataLines:
    def test_c_record_matched_to_b_record(self):
        lines = [
            "C;001;12345;1;extra;LOT 99 DP 12345;extra",
            _current_b_line(),
        ]
        records = extract.parse_data_lines(lines)
        assert len(records) == 1
        assert records[0]["Property legal description"] == "LOT 99 DP 12345"

    def test_b_without_c_has_none_legal_description(self):
        records = extract.parse_data_lines([_current_b_line()])
        assert records[0]["Property legal description"] is None

    def test_non_b_non_c_lines_ignored(self):
        assert extract.parse_data_lines(["A;header", "D;footer", ""]) == []

    def test_multiple_properties_parsed(self):
        lines = [_current_b_line(prop_id="1"), _current_b_line(prop_id="2")]
        assert len(extract.parse_data_lines(lines)) == 2


# ---------------------------------------------------------------------------
# create_and_clean_dataframe
# ---------------------------------------------------------------------------

class TestCreateAndCleanDataframe:
    def test_empty_input_returns_empty_dataframe(self):
        assert extract.create_and_clean_dataframe([]).empty

    def test_district_code_in_output(self):
        df = extract.create_and_clean_dataframe([_make_record()])
        assert "District code" in df.columns

    def test_hectare_conversion(self):
        records = [
            _make_record(**{"Property ID": "H1", "Area": "1", "Area type": "H"}),
            _make_record(**{"Property ID": "M1", "Area": "500", "Area type": "M"}),
        ]
        df = extract.create_and_clean_dataframe(records)
        assert df.loc[df["Property ID"] == "H1", "Area"].iloc[0] == 10000.0
        assert df.loc[df["Property ID"] == "M1", "Area"].iloc[0] == 500.0

    def test_hectare_conversion_after_date_filtering(self):
        # Verifies the fix works correctly even when the DataFrame index has gaps
        # from prior date filtering
        future = (date.today() + timedelta(days=30)).strftime('%Y%m%d')
        records = [
            _make_record(**{"Property ID": "FUTURE", "Contract date": future}),
            _make_record(**{"Property ID": "H1", "Area": "2", "Area type": "H"}),
            _make_record(**{"Property ID": "M1", "Area": "300", "Area type": "M"}),
        ]
        with patch.object(extract, 'FILTER_FUTURE_DATES', True), \
             patch.object(extract, 'FILTER_PRE_1990_DATES', False):
            df = extract.create_and_clean_dataframe(records)
        # FUTURE row should be removed, creating index gaps
        assert "FUTURE" not in df["Property ID"].values
        assert df.loc[df["Property ID"] == "H1", "Area"].iloc[0] == 20000.0
        assert df.loc[df["Property ID"] == "M1", "Area"].iloc[0] == 300.0

    def test_deduplication_removes_identical_records(self):
        records = [_make_record(), _make_record()]
        df = extract.create_and_clean_dataframe(records)
        assert len(df) == 1

    def test_deduplication_keeps_distinct_records(self):
        records = [
            _make_record(**{"Property ID": "AAA", "Purchase price": "1000000"}),
            _make_record(**{"Property ID": "BBB", "Purchase price": "2000000"}),
        ]
        df = extract.create_and_clean_dataframe(records)
        assert len(df) == 2

    def test_future_contract_dates_filtered(self):
        future = (date.today() + timedelta(days=30)).strftime('%Y%m%d')
        records = [
            _make_record(**{"Property ID": "PAST", "Contract date": "20240101"}),
            _make_record(**{"Property ID": "FUTURE", "Contract date": future}),
        ]
        df = extract.create_and_clean_dataframe(records)
        assert "FUTURE" not in df["Property ID"].values
        assert "PAST" in df["Property ID"].values

    def test_nat_dates_preserved_by_future_date_filter(self):
        records = [
            _make_record(**{"Property ID": "UNPARSEABLE", "Contract date": "NOT_A_DATE"}),
            _make_record(**{"Property ID": "VALID", "Contract date": "20240101"}),
        ]
        with patch.object(extract, 'FILTER_FUTURE_DATES', True), \
             patch.object(extract, 'FILTER_PRE_1990_DATES', False):
            df = extract.create_and_clean_dataframe(records)
        assert "UNPARSEABLE" in df["Property ID"].values
        assert "VALID" in df["Property ID"].values

    def test_string_columns_are_title_cased(self):
        df = extract.create_and_clean_dataframe([_make_record()])
        assert df["Property locality"].iloc[0] == "Sydney"
        assert df["Property street name"].iloc[0] == "Main St"

    def test_purchase_price_is_numeric(self):
        df = extract.create_and_clean_dataframe([_make_record()])
        assert pd.api.types.is_numeric_dtype(df["Purchase price"])


# ---------------------------------------------------------------------------
# extract_dat_lines_from_zip
# ---------------------------------------------------------------------------

class TestExtractDatLinesFromZip:
    def test_reads_dat_from_top_level(self, tmp_path):
        content = "B;001;12345;1;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x\nC;001;12345;1;x;desc;x"
        zip_path = _make_zip_with_dat(content, tmp_path)
        lines = extract.extract_dat_lines_from_zip(zip_path)
        assert len(lines) == 2

    def test_reads_dat_from_nested_zip(self, tmp_path):
        content = "B;001;12345;1;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x;x"
        zip_path = _make_zip_with_dat(content, tmp_path, inner=True)
        lines = extract.extract_dat_lines_from_zip(zip_path)
        assert len(lines) == 1

    def test_missing_file_returns_empty(self, tmp_path):
        lines = extract.extract_dat_lines_from_zip(str(tmp_path / "nonexistent.zip"))
        assert lines == []

    def test_bad_zip_returns_empty(self, tmp_path):
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_bytes(b"not a zip file")
        lines = extract.extract_dat_lines_from_zip(str(bad_zip))
        assert lines == []
