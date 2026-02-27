import logging
import io
import zipfile
import csv
import json
import pandas as pd
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# --- Constants ---
DATA_DIR = "./data"
FINAL_CSV_PATH = "extract-3-very-clean.csv"
LOG_FILE_PATH = "propsales.log"
PROGRESS_FILE_PATH = "extract-progress.json"
# --- Filtering Controls ---
# Set to True to remove records with contract dates in the future
FILTER_FUTURE_DATES = True
# Set to True to remove records with contract dates before EARLIEST_DATE
FILTER_PRE_1990_DATES = True
EARLIEST_DATE = '1990-01-01'


# --- Configure logging ---
# Set up logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)

def get_zip_signature(zip_filepath):
    """Returns a stable signature for a zip file based on size and mtime."""
    stat_info = zip_filepath.stat()
    return {
        "size": stat_info.st_size,
        "mtime_ns": stat_info.st_mtime_ns,
    }

def load_progress_state(progress_path, output_path, zip_files):
    """Loads cached extraction progress and validates it against current zip files."""
    empty_state = {
        "version": 1,
        "csv_header_written": False,
        "processed_zips": {}
    }

    if not progress_path.exists():
        if output_path.exists():
            logging.warning(
                f"Found existing output {output_path} without {progress_path}; "
                "starting full rebuild to avoid duplicate rows."
            )
        return empty_state, False

    try:
        loaded_state = json.loads(progress_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning(f"Unable to read progress file {progress_path}: {exc}. Starting full rebuild.")
        return empty_state, False

    processed_zips = loaded_state.get("processed_zips")
    if not isinstance(processed_zips, dict):
        logging.warning(f"Invalid progress file format in {progress_path}. Starting full rebuild.")
        return empty_state, False

    if not output_path.exists():
        if processed_zips:
            logging.warning(
                f"Progress file {progress_path} exists but output {output_path} is missing; "
                "starting full rebuild."
            )
        return empty_state, False

    zip_file_map = {zip_file.name: zip_file for zip_file in zip_files}
    for zip_name, cached in processed_zips.items():
        zip_path = zip_file_map.get(zip_name)
        if zip_path is None:
            logging.warning(
                f"Progress references missing zip {zip_name}; starting full rebuild for consistency."
            )
            return empty_state, False

        current_sig = get_zip_signature(zip_path)
        if (
            cached.get("size") != current_sig["size"] or
            cached.get("mtime_ns") != current_sig["mtime_ns"]
        ):
            logging.warning(
                f"Zip changed since last run ({zip_name}); starting full rebuild for consistency."
            )
            return empty_state, False

    normalized_state = {
        "version": 1,
        "csv_header_written": bool(
            loaded_state.get("csv_header_written", output_path.stat().st_size > 0)
        ),
        "processed_zips": processed_zips
    }
    should_resume = bool(processed_zips)
    return normalized_state, should_resume

def save_progress_state(progress_path, state):
    """Persists extraction progress atomically."""
    tmp_path = progress_path.with_suffix(progress_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp_path.replace(progress_path)

def extract_dat_lines_from_zip(zip_filepath):
    """Yields lines from .dat files in a zip file, including nested zip files."""
    def decode_content(raw_content, source_label):
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        logging.warning(f"Skipping undecodable file content: {source_label}")
        return None

    def yield_lines_from_content(raw_content, source_label):
        decoded = decode_content(raw_content, source_label)
        if decoded is None:
            return
        for line in decoded.splitlines():
            yield line

    def yield_dat_lines_from_nested_zip(raw_nested_zip, source_label):
        try:
            with zipfile.ZipFile(io.BytesIO(raw_nested_zip)) as nested_zip:
                for nested_name in nested_zip.namelist():
                    if nested_name.lower().endswith(".dat"):
                        try:
                            nested_content = nested_zip.read(nested_name)
                            yield from yield_lines_from_content(nested_content, f"{source_label}:{nested_name}")
                        except KeyError:
                            logging.warning(f"Unable to read nested file: {source_label}:{nested_name}")
        except zipfile.BadZipFile:
            logging.warning(f"Skipping invalid nested zip: {source_label}")

    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_file:
            for file_name in zip_file.namelist():
                if file_name.lower().endswith(".dat"):
                    try:
                        content = zip_file.read(file_name)
                        yield from yield_lines_from_content(content, f"{zip_filepath}:{file_name}")
                    except KeyError:
                        logging.warning(f"Unable to read file in archive {zip_filepath}: {file_name}")
                elif file_name.lower().endswith(".zip"):
                    try:
                        with zip_file.open(file_name) as nested_zip_file:
                            nested_zip_content = nested_zip_file.read()
                            yield from yield_dat_lines_from_nested_zip(nested_zip_content, f"{zip_filepath}:{file_name}")
                    except zipfile.BadZipFile:
                        logging.warning(f"Skipping invalid nested zip in {zip_filepath}: {file_name}")
                    except KeyError:
                        logging.warning(f"Unable to open nested zip in {zip_filepath}: {file_name}")
    except FileNotFoundError:
        logging.error(f"File not found: {zip_filepath}")
    except zipfile.BadZipFile:
        logging.error(f"Bad zip file: {zip_filepath}")

def parse_data_lines(lines):
    """Parses raw PSI lines into records and returns (records, total_lines_seen)."""
    processed_records = []
    legal_descriptions = {}
    pending_current_records = defaultdict(list)
    line_count = 0

    for line in lines:
        line_count += 1
        line = line.strip()
        if not line:
            continue

        if line.startswith("C;"):
            parts = [p.strip() for p in line.split(";")]
            if len(parts) >= 6:
                key = (parts[1], parts[2], parts[3])
                legal_descriptions[key] = parts[5]
                if key in pending_current_records:
                    for pending_record in pending_current_records.pop(key):
                        pending_record["Property legal description"] = parts[5]
            continue

        if not line.startswith("B;"):
            continue

        parts = [p.strip() for p in line.split(";")]

        is_archived = len(parts) > 2 and not parts[2].isdigit()

        record = None
        if is_archived:
            record = parse_archived_record(parts)
        else:
            record = parse_current_record(parts)
            if record:
                key = (record.get("District code"), record.get("Property ID"), record.get("Sale counter"))
                if key in legal_descriptions:
                    record["Property legal description"] = legal_descriptions[key]
                else:
                    pending_current_records[key].append(record)
        
        if record:
            processed_records.append(record)

    return processed_records, line_count

def parse_current_record(parts):
    """Parses a 'B' record from the current data format."""
    if len(parts) < 24:
        return None
    return {
        "District code": parts[1],
        "Property ID": parts[2],
        "Sale counter": parts[3],
        "Download date / time": parts[4],
        "Property name": parts[5],
        "Property unit number": parts[6],
        "Property house number": parts[7],
        "Property street name": parts[8],
        "Property locality": parts[9],
        "Property post code": parts[10],
        "Area": parts[11],
        "Area type": parts[12],
        "Contract date": parts[13],
        "Settlement date": parts[14],
        "Purchase price": parts[15],
        "Zoning": parts[16],
        "Nature of property": parts[17],
        "Primary purpose": parts[18],
        "Strata lot number": parts[19],
        "Dealing number": parts[23],
        "Property legal description": None # To be filled in later
    }

def parse_archived_record(parts):
    """Parses a 'B' record from the archived data format."""
    if len(parts) < 18:
        return None
    
    contract_date_str = ""
    try:
        contract_date = datetime.strptime(parts[10], "%d/%m/%Y")
        contract_date_str = contract_date.strftime("%Y%m%d")
    except ValueError:
        contract_date_str = parts[10]

    return {
        "District code": parts[1],
        "Property ID": parts[4],
        "Sale counter": None,
        "Download date / time": None,
        "Property name": None,
        "Property unit number": parts[5],
        "Property house number": parts[6],
        "Property street name": parts[7],
        "Property locality": parts[8],
        "Property post code": parts[9],
        "Area": parts[13],
        "Area type": parts[14],
        "Contract date": contract_date_str,
        "Settlement date": None, # Not available in archived format
        "Purchase price": parts[11],
        "Zoning": parts[17],
        "Nature of property": None,
        "Primary purpose": None,
        "Strata lot number": None,
        "Dealing number": None,
        "Property legal description": parts[12]
    }

def create_and_clean_dataframe(records):
    """
    Creates and cleans a pandas DataFrame from a list of records.

    Args:
        records (list): A list of dictionaries representing parsed records.

    Returns:
        pandas.DataFrame: A cleaned and processed DataFrame.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    df['Contract date'] = pd.to_datetime(df['Contract date'], format='%Y%m%d', errors='coerce')
    df['Settlement date'] = pd.to_datetime(df['Settlement date'], format='%Y%m%d', errors='coerce')

    numeric_cols = ['Purchase price', 'Area', 'Property post code']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    if FILTER_FUTURE_DATES:
        today = pd.to_datetime('today').normalize()
        original_count = len(df)
        df = df[df['Contract date'] <= today].copy()
        removed_count = original_count - len(df)
        if removed_count > 0:
            logging.info(f"Removed {removed_count} records with future contract dates.")

    if FILTER_PRE_1990_DATES:
        earliest_date = pd.to_datetime(EARLIEST_DATE).normalize()
        original_count = len(df)
        df = df[(df['Contract date'] >= earliest_date) | (df['Contract date'].isna())].copy()
        removed_count = original_count - len(df)
        if removed_count > 0:
            logging.info(f"Removed {removed_count} records with contract dates before {EARLIEST_DATE}.")

    df['Area type'] = df['Area type'].astype('string').str.strip().str.upper()
    df.loc[df['Area type'] == 'H', 'Area'] = df['Area'] * 10000

    string_cols = ['Property name', 'Property street name', 'Property locality', 'Primary purpose']
    for col in string_cols:
        df[col] = df[col].astype('string').str.strip().str.title()

    final_columns = [
        "Property ID", "Sale counter", "Download date / time", "Property name", 
        "Property unit number", "Property house number", "Property street name", 
        "Property locality", "Property post code", "Area", "Area type", 
        "Contract date", "Settlement date", "Purchase price", "Zoning", 
        "Nature of property", "Primary purpose", "Strata lot number", 
        "Dealing number", "Property legal description"
    ]
    for col in final_columns:
        if col not in df.columns:
            df[col] = None
            
    return df[final_columns]

def main():
    """Main function to orchestrate the data extraction, processing, and export."""
    start_time = time.time()
    logging.info('Start: Extracting and processing data.')

    data_dir = Path(DATA_DIR)
    output_path = Path(FINAL_CSV_PATH)
    progress_path = Path(PROGRESS_FILE_PATH)

    if not data_dir.exists():
        logging.error(f"Data directory not found: {DATA_DIR}")
        return

    zip_files = sorted(data_dir.glob("*.zip"))
    total_lines = 0
    total_parsed_records = 0
    total_exported_records = 0

    progress_state, should_resume = load_progress_state(progress_path, output_path, zip_files)
    if should_resume:
        logging.info(
            f"Resuming from cached progress: {len(progress_state['processed_zips'])} zip files already completed."
        )
    else:
        progress_state = {
            "version": 1,
            "csv_header_written": False,
            "processed_zips": {}
        }
        if output_path.exists():
            output_path.unlink()
        save_progress_state(progress_path, progress_state)

    csv_header_written = (
        progress_state["csv_header_written"] and
        output_path.exists() and
        output_path.stat().st_size > 0
    )
    processed_zips = progress_state["processed_zips"]

    logging.info("Begin: Extracting and parsing zip files.")
    for zip_filepath in zip_files:
        current_sig = get_zip_signature(zip_filepath)
        cached = processed_zips.get(zip_filepath.name)
        if (
            cached and
            cached.get("size") == current_sig["size"] and
            cached.get("mtime_ns") == current_sig["mtime_ns"]
        ):
            total_lines += int(cached.get("line_count", 0))
            total_parsed_records += int(cached.get("parsed_records", 0))
            total_exported_records += int(cached.get("exported_records", 0))
            logging.info(f"Skipping already processed: {zip_filepath}")
            continue

        logging.info(f"Extracting from: {zip_filepath}")
        parsed_records, file_line_count = parse_data_lines(extract_dat_lines_from_zip(zip_filepath))
        total_lines += file_line_count
        total_parsed_records += len(parsed_records)

        exported_records = 0

        if not parsed_records:
            logging.info(f"No records parsed from {zip_filepath}; skipping export for this file.")
        else:
            df = create_and_clean_dataframe(parsed_records)
            if df.empty:
                logging.info(f"No rows remaining after cleaning for {zip_filepath}; skipping export.")
            else:
                df.to_csv(
                    FINAL_CSV_PATH,
                    mode='a',
                    header=not csv_header_written,
                    index=False,
                    quoting=csv.QUOTE_ALL
                )
                csv_header_written = True
                exported_records = len(df)
                total_exported_records += exported_records

        processed_zips[zip_filepath.name] = {
            "size": current_sig["size"],
            "mtime_ns": current_sig["mtime_ns"],
            "line_count": file_line_count,
            "parsed_records": len(parsed_records),
            "exported_records": exported_records,
            "completed_at": datetime.utcnow().isoformat() + "Z"
        }
        progress_state["csv_header_written"] = csv_header_written
        save_progress_state(progress_path, progress_state)

        logging.info(
            f"Completed {zip_filepath}: {file_line_count} lines, "
            f"{len(parsed_records)} parsed, {exported_records} exported."
        )

    logging.info(f"Extraction complete. Found {total_lines} total lines.")
    logging.info(f"Parsing complete. Found {total_parsed_records} property records.")
    logging.info(f"Export complete. Wrote {total_exported_records} records to {FINAL_CSV_PATH}.")
    logging.info(f"{int(time.time() - start_time)} seconds elapsed.")

    if not csv_header_written:
        logging.warning("No data to export; the final CSV file will not be created.")

    logging.info("Complete: Data has been extracted and processed.")
    logging.info(f"Total elapsed time was {int(time.time() - start_time)} seconds.")

if __name__ == "__main__":
    main()
