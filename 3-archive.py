import logging
import time
import zipfile
from datetime import datetime
from pathlib import Path
import shutil

#
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("propsales.log"), logging.StreamHandler()])

def main():
	logging.info('Creating zip archive')
	start = time.time()

	output_dir = Path('data3')
	output_dir.mkdir(parents=True, exist_ok=True)

	name_original = Path('data2/extract-3-very-clean.csv')
	name_new = 'nsw-property-sales-data-updated' + datetime.now().strftime('%Y%m%d')
	dated_csv_name = name_new + '.csv'
	dated_zip = output_dir / (name_new + '.zip')
	archive_zip = output_dir / 'archive.zip'

	if not name_original.exists():
		raise FileNotFoundError(f"Expected file not found: {name_original}")

	with zipfile.ZipFile(dated_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
		zip_file.write(name_original, arcname=dated_csv_name)

	archive_zip_tmp = archive_zip.with_suffix('.zip.tmp')
	shutil.copy2(dated_zip, archive_zip_tmp)
	archive_zip_tmp.replace(archive_zip)

	logging.info("Complete: zip archive has been created.")
	logging.info('Total elapsed time was ' + str(int(time.time() - start)) + " seconds")

if __name__ == "__main__":
	main()