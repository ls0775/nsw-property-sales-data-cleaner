import logging
import shutil
import time
import os
import zipfile
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("propsales.log"), logging.StreamHandler()]
)

CSV_PATH = 'extract-3-very-clean.csv'
OUTPUT_DIR = 'output'


def create_archive(csv_path=CSV_PATH, output_dir=OUTPUT_DIR):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source CSV not found: {csv_path}. Run 2-extract.py first.")

    os.makedirs(output_dir, exist_ok=True)

    dated_name = 'nsw-property-sales-data-updated' + datetime.now().strftime('%Y%m%d')
    zip_path = os.path.join(output_dir, dated_name + '.zip')

    with zipfile.ZipFile(zip_path, mode='w') as zf:
        zf.write(csv_path, dated_name + '.csv', compress_type=zipfile.ZIP_DEFLATED)

    # Remove previous dated zips, keeping only the current run
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if (fname.startswith('nsw-property-sales-data-updated')
                and fname.endswith('.zip')
                and fpath != zip_path):
            os.remove(fpath)
            logging.info(f"Removed old archive: {fpath}")

    # Update the generic latest copy
    shutil.copy2(zip_path, os.path.join(output_dir, 'archive.zip'))

    return zip_path


def main():
    logging.info('Creating zip archive')
    start = time.time()
    zip_path = create_archive()
    logging.info(f"Complete: zip archive created: {zip_path}")
    logging.info(f'Total elapsed time was {int(time.time() - start)} seconds')


if __name__ == "__main__":
    main()
