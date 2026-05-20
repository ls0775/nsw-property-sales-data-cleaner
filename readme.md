As a human who wants to buy a house and is interested in data, I want to analyse sales data for the suburbs I'm interested in so that I can make better offers.

The data from the bulk NSW Valuer General's Property Sales Information (PSI) makes it really hard to download and analyse. And a subscription to Core Logic is really expensive. So here we are.

Basically:

* Python to download the latest copy of the (.zip) data files as they are regularly updated

* Python to extract the data from the data (.zip) files and delete all the junk

* Jupyter to do whatever analysis you want.

## Install

* Install Python 3
* Clone or copy this project to a folder
* Open a terminal in the project folder
* Create a virtual environment: `python3 -m venv .venv`
* Activate it: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate.bat` (Windows)
* Install dependencies: `pip install -r requirements.txt`

## Usage

Run the three scripts in order:

```bash
# 1. Download ~35 years of data from the NSW Valuer General (~45 seconds, ~390 MB)
.venv/bin/python 1-download.py

# 2. Extract, parse, clean, and deduplicate all records (~4 minutes, produces ~1 GB CSV)
.venv/bin/python 2-extract.py

# 3. Archive the CSV into a dated zip in the output/ directory (~30 seconds)
.venv/bin/python 3-archive.py

# 4. Open the analysis notebook
.venv/bin/jupyter notebook analysis.ipynb
```

### Output files

| File | Description |
|---|---|
| `data/*.zip` | Raw downloaded zip files (do not delete — reruns skip existing files) |
| `extract-3-very-clean.csv` | Cleaned and deduplicated property sales records |
| `output/nsw-property-sales-data-updated<YYYYMMDD>.zip` | Compressed archive of this run's CSV |
| `output/archive.zip` | Always points to the most recent run's archive |
| `propsales.log` | Combined log from all three scripts |

Re-running step 1 skips files that already exist. Re-running step 3 removes the previous dated zip from `output/`, keeping only the current run alongside `archive.zip`.

### Data coverage

* **Yearly files**: 1991 to last completed year (35 years)
* **Weekly files**: first Monday of the current year up to 14 days before today
* **Both formats supported**: archived format (1990–2001) and current format (2001–present)
* Records that appear in both yearly and weekly files are deduplicated automatically

### Running the tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Analysis notebook

`analysis.ipynb` contains two sections:

### Area analysis (existing)
Filter by suburb(s), postcode range, price, area, zoning, and date to produce:
- Price histogram
- Price vs size scatter over time
- Price trend with rolling average
- Monthly median price
- Monthly sales volume

### Street-level query with spatial map (new)
Set a street name, suburb, postcode, and date range to:
- Pull all matching sales from the dataset
- Geocode each address via OpenStreetMap (Nominatim, free, no API key)
- Plot every sale on an interactive street-level map, coloured and sized by price
- Hover to see address, price, date, area, and zoning

Geocoded addresses are cached in `geocode_cache.csv` — the first run for a street takes ~1 second per unique address; subsequent runs are instant.

**Example query — King Street, Mascot, all of 2020:**
```python
query_street     = 'King St'
query_locality   = 'Mascot'
query_postcode   = 2020
query_start_date = '2020-01-01'
query_end_date   = '2020-12-31'
```

## Output CSV columns

| Column | Notes |
|---|---|
| `District code` | NSW Valuer General district |
| `Property ID` | Unique property identifier |
| `Sale counter` | Current format only |
| `Download date / time` | Current format only |
| `Property name` | |
| `Property unit number` | |
| `Property house number` | |
| `Property street name` | Title-cased |
| `Property locality` | Title-cased (suburb) |
| `Property post code` | |
| `Area` | Square metres (hectares converted automatically) |
| `Area type` | `M` = square metres, `H` = hectares (before conversion) |
| `Contract date` | |
| `Settlement date` | Current format only |
| `Purchase price` | |
| `Zoning` | |
| `Nature of property` | Current format only |
| `Primary purpose` | Title-cased, current format only |
| `Strata lot number` | Current format only |
| `Dealing number` | Current format only |
| `Property legal description` | |

## Valuer General documentation

Sales data is available online via the Valuer General's [Bulk property sales information website](https://valuation.property.nsw.gov.au/embed/propertySalesInformation).

### General information
* [Instructions](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Instructions_V2.pdf) (PDF 63KB)

### Technical documentation
* [Current property sales data file format (2001 to Current)](/Valuer%20General%20documentation/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf) (PDF 75KB)

* [Archived property sales data file format (1990 to 2001)](/Valuer%20General%20documentation/Archived_Property_Sales_Data_File_Format_1990_to_2001_V2.pdf) (PDF 72KB)

* [Data elements](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Data_Elements_V3.pdf) (PDF 66KB)

* [Property sales data file (District Codes and names)](/Valuer%20General%20documentation/Property_Sales_Data_File_District_Codes_and_Names.pdf) (PDF 75KB)

* [Property sales data file (Zone Codes and descriptions)](/Valuer%20General%20documentation/Property_Sales_Data_File_Zone_Codes_and_Descriptions_V2.pdf) (PDF 61KB)

* [Property sales information data files user guide](/Valuer%20General%20documentation/Property_Sales_Information_Data_Files_User_guide.pdf) (PDF 1.9MB)
