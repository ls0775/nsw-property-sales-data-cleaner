import logging
import time
from pathlib import Path

import pandas as pd

INPUT_CSV_PATH = Path("data2/extract-3-very-clean.csv")
OUTPUT_PARQUET_PATH = Path("data4/extract-3-very-clean.parquet")
LOG_FILE_PATH = Path("propsales.log")
CHUNK_SIZE = 250_000

FINAL_COLUMNS = [
    "Property ID", "Sale counter", "Download date / time", "Property name",
    "Property unit number", "Property house number", "Property street name",
    "Property locality", "Property post code", "Area", "Area type",
    "Contract date", "Settlement date", "Purchase price", "Zoning",
    "Nature of property", "Primary purpose", "Strata lot number",
    "Dealing number", "Property legal description"
]

DATE_COLUMNS = ["Contract date", "Settlement date"]
NUMERIC_COLUMNS = ["Purchase price", "Area", "Property post code"]


def build_parquet_schema(pa_module):
    return pa_module.schema([
        ("Property ID", pa_module.large_string()),
        ("Sale counter", pa_module.large_string()),
        ("Download date / time", pa_module.large_string()),
        ("Property name", pa_module.large_string()),
        ("Property unit number", pa_module.large_string()),
        ("Property house number", pa_module.large_string()),
        ("Property street name", pa_module.large_string()),
        ("Property locality", pa_module.large_string()),
        ("Property post code", pa_module.float64()),
        ("Area", pa_module.float64()),
        ("Area type", pa_module.large_string()),
        ("Contract date", pa_module.timestamp("us")),
        ("Settlement date", pa_module.timestamp("us")),
        ("Purchase price", pa_module.float64()),
        ("Zoning", pa_module.large_string()),
        ("Nature of property", pa_module.large_string()),
        ("Primary purpose", pa_module.large_string()),
        ("Strata lot number", pa_module.large_string()),
        ("Dealing number", pa_module.large_string()),
        ("Property legal description", pa_module.large_string()),
    ])


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE_PATH),
            logging.StreamHandler()
        ]
    )


def normalize_chunk(df: pd.DataFrame) -> pd.DataFrame:
    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[FINAL_COLUMNS].copy()

    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")

    for col in FINAL_COLUMNS:
        if col not in DATE_COLUMNS and col not in NUMERIC_COLUMNS:
            df[col] = df[col].astype("string")

    return df


def main():
    configure_logging()
    start = time.time()

    logging.info("Start: Transforming CSV to Parquet")

    if not INPUT_CSV_PATH.exists():
        raise FileNotFoundError(f"Expected file not found: {INPUT_CSV_PATH}")

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError(
            "pyarrow is required for Parquet export. Install it with: pip install pyarrow"
        ) from exc

    parquet_schema = build_parquet_schema(pa)

    OUTPUT_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_output = OUTPUT_PARQUET_PATH.with_suffix(".parquet.tmp")
    if temp_output.exists():
        temp_output.unlink()

    writer = None
    chunks_processed = 0
    total_rows = 0

    try:
        for chunk in pd.read_csv(INPUT_CSV_PATH, chunksize=CHUNK_SIZE, low_memory=False):
            normalized = normalize_chunk(chunk)
            table = pa.Table.from_pandas(
                normalized,
                schema=parquet_schema,
                preserve_index=False
            )

            if writer is None:
                writer = pq.ParquetWriter(temp_output, parquet_schema, compression="snappy")

            writer.write_table(table)
            chunks_processed += 1
            total_rows += len(normalized)

            logging.info(
                f"Processed chunk {chunks_processed}: {len(normalized)} rows (total {total_rows})"
            )
    finally:
        if writer is not None:
            writer.close()

    temp_output.replace(OUTPUT_PARQUET_PATH)

    logging.info(f"Complete: Created {OUTPUT_PARQUET_PATH}")
    logging.info(f"Rows written: {total_rows}")
    logging.info(f"Total elapsed time was {int(time.time() - start)} seconds")


if __name__ == "__main__":
    main()
