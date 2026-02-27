import time
import urllib.request
from urllib.error import URLError, HTTPError
from datetime import date, timedelta
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import shutil
import zipfile

# Constants
URL_BASE = 'https://www.valuergeneral.nsw.gov.au/__psi/'
WEEKLY_URL = URL_BASE + 'weekly/'
YEARLY_URL = URL_BASE + 'yearly/'
DOWNLOAD_DIR = 'data/'
YEARS_TO_COLLECT = 35
RECENT_WEEKS_TO_EXCLUDE = 14  # Number of days to exclude from recent weekly downloads.
RETRY_ATTEMPTS = 3
MAX_WORKERS = 8
REQUEST_TIMEOUT_SECONDS = 60

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("propsales.log"), logging.StreamHandler()])

def download_file(url, filepath):
    """Downloads a file from a URL to a specified filepath."""
    if filepath.exists() and filepath.stat().st_size > 0:
        logging.info(f'Skipping existing file: {filepath.name}')
        return True

    for attempt in range(RETRY_ATTEMPTS):
        try:
            logging.info(f'Downloading {url} to {filepath} (attempt {attempt + 1})')
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir=filepath.parent) as temp_file:
                    shutil.copyfileobj(response, temp_file)
                    temp_path = Path(temp_file.name)

            if temp_path.stat().st_size == 0:
                temp_path.unlink(missing_ok=True)
                raise ValueError('Downloaded file is empty')

            if filepath.suffix.lower() == '.zip' and not zipfile.is_zipfile(temp_path):
                temp_path.unlink(missing_ok=True)
                raise ValueError('Downloaded file is not a valid zip archive')

            temp_path.replace(filepath)
            logging.info(f'Downloaded {url} to {filepath}')
            return True
        except (URLError, HTTPError, TimeoutError, ValueError) as e:
            logging.error(f'Error downloading {url} (attempt {attempt + 1}): {e}')
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
            else:
                return False
        except Exception as e:
            logging.error(f'An unexpected error occurred during download {url} : {e}')
            return False
    return False


def build_weekly_jobs(start_date, end_date):
    """Build (url, filepath) tuples for weekly downloads."""
    jobs = []
    adjusted_end_date = end_date - timedelta(days=RECENT_WEEKS_TO_EXCLUDE)
    current_date = start_date
    while current_date < adjusted_end_date:
        filename = current_date.strftime('%Y%m%d') + '.zip'
        jobs.append((WEEKLY_URL + filename, Path(DOWNLOAD_DIR) / filename))
        current_date += timedelta(days=7)
    return jobs


def build_yearly_jobs(start_year, end_year):
    """Build (url, filepath) tuples for yearly downloads."""
    jobs = []
    for year in range(start_year, end_year):
        filename = str(year) + '.zip'
        jobs.append((YEARLY_URL + filename, Path(DOWNLOAD_DIR) / filename))
    return jobs


def run_download_jobs(jobs):
    """Run all download jobs concurrently with bounded workers."""
    if not jobs:
        logging.info('No download jobs to run.')
        return

    filtered_jobs = [(url, filepath) for url, filepath in jobs if not (filepath.exists() and filepath.stat().st_size > 0)]
    skipped_count = len(jobs) - len(filtered_jobs)
    if skipped_count:
        logging.info(f'Skipping {skipped_count} existing files.')

    if not filtered_jobs:
        logging.info('All target files are already present.')
        return

    success_count = 0
    failure_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(download_file, url, filepath) for url, filepath in filtered_jobs]
        for future in as_completed(futures):
            if future.result():
                success_count += 1
            else:
                failure_count += 1

    logging.info(f'Download summary: {success_count} succeeded, {failure_count} failed.')

def main():
    """Main function to download data."""
    logging.info('Start downloading the data')
    start_time = time.time()

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Using directory: {download_dir}")

    today = date.today()
    start_weekly_date = date(today.year, 1, 7) - timedelta(days=date(today.year, 1, 7).weekday())
    end_weekly_date = today

    weekly_jobs = build_weekly_jobs(start_weekly_date, end_weekly_date)
    yearly_jobs = build_yearly_jobs(today.year - YEARS_TO_COLLECT, today.year)
    all_jobs = weekly_jobs + yearly_jobs
    logging.info(f'Prepared {len(weekly_jobs)} weekly and {len(yearly_jobs)} yearly downloads.')

    run_download_jobs(all_jobs)

    logging.info('Complete: the data has been downloaded.')
    logging.info(f'Total elapsed time was {int(time.time() - start_time)} seconds')

if __name__ == "__main__":
    main()