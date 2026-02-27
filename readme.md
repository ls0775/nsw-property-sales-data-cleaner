As a human who wants to buy a house and is interested in data, I want to analyse sales data for the suburbs I'm interested in so that I can make better offers.

The data from the bulk NSW Valuer General's Property Sales Information (PSI) makes it really hard to download and analyse. And a subscription to Core Logic is really expensive. So here we are.

Basically:

* Python to download the latest copy of the (.zip) data files as they are regularly updated

* Python to extract the data from the data (.zip) files and delete all the junk

* Jupyter to do whatever analysis you want.

The scripts are now structured to be safer and more repeatable, while keeping output files and schema unchanged.

## Install

Recommended with VS Code:

* Install Python 3.10+
* Copy/clone this project and open it in VS Code
* In a terminal at the project root, create a virtual environment:
	* Linux/macOS: `python3 -m venv .venv`
	* Windows: `py -3 -m venv .venv`
* Activate it:
	* Linux/macOS: `source .venv/bin/activate`
	* Windows (PowerShell): `.venv\Scripts\Activate.ps1`
* Install dependencies: `pip install -r requirements.txt`

## Run pipeline

Run scripts in this order:

1. `python 1-download.py`
2. `python 2-extract.py`
3. `python 3-archive.py`

Outputs are:

* `extract-3-very-clean.csv` (clean dataset used by notebook)
* `nsw-property-sales-data-updatedYYYYMMDD.zip` (dated archive)
* `archive.zip` (latest archive copy)

## Valuer General documentation

Sales data is available online via the Valuer General's [Bulk property sales information website](https://valuation.property.nsw.gov.au/embed/propertySalesInformation).

I have included their documentation as part of this repository.

### General information
* [Instructions](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Instructions_V2.pdf) (PDF 63KB)

### Technical documentation
* [Current property sales data file format (2001 to Current)](/Valuer%20General%20documentation/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf) (PDF 75KB)

* [Archived property sales data file format (1990 to 2001)](/Valuer%20General%20documentation/Archived_Property_Sales_Data_File_Format_1990_to_2001_V2.pdf) (PDF 72KB)

* [Data elements](/Valuer%20General%20documentation/Property_Sales_Data_File_-_Data_Elements_V3.pdf) (PDF 66KB)

* [Property sales data file (District Codes and names)](/Valuer%20General%20documentation/Property_Sales_Data_File_District_Codes_and_Names.pdf) (PDF 75KB)

* [Property sales data file (Zone Codes and descriptions)](/Valuer%20General%20documentation/Property_Sales_Data_File_Zone_Codes_and_Descriptions_V2.pdf) (PDF 61KB)

* [Property sales information data files user guide](/Valuer%20General%20documentation/Property_Sales_Information_Data_Files_User_guide.pdf) (PDF 1.9MB)
