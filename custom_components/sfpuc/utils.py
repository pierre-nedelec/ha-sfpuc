from datetime import datetime
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def get_hidden_fields_from_page(page_html: str) -> dict:
    """Extract hidden fields from a page."""
    soup = BeautifulSoup(page_html, "html.parser")
    viewstate = soup.find("input", {"id": "__VIEWSTATE"})["value"]
    eventvalidation = soup.find("input", {"id": "__EVENTVALIDATION"})["value"]
    viewstategenerator = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]

    return {
        "__VIEWSTATE": viewstate,
        "__EVENTVALIDATION": eventvalidation,
        "__VIEWSTATEGENERATOR": viewstategenerator,
    }


def parse_download_data(content: bytes, start_date: str) -> dict:
    """Parse the download data from SFPUC and return it as a dictionary.

    Args:
        content (bytes): The content of the download object.
        start_date (str): The start date in MM/DD/YYYY format.

    Returns:
        dict: Parsed water usage data with timestamps and consumption.

    """
    # Decode the content (assuming it's in a CSV-like format)
    decoded_csv = content.decode("utf-8")
    decoded_csv = decoded_csv.replace("\t", ",")

    # Initialize a dictionary to store the parsed data
    water_usage_data = {}
    pacific_tz = ZoneInfo("America/Los_Angeles")

    # Split the decoded content into lines
    lines = decoded_csv.split("\n")

    # Skip the first line if it's a header
    for line in lines[1:]:
        if line.strip():
            hour, consumption = line.split(",")
            date_time_str = f"{start_date} {hour}"

            # Parse the datetime string
            date_time = datetime.strptime(date_time_str, "%m/%d/%Y %I %p")
            date_time = date_time.replace(tzinfo=pacific_tz)

            # Add the parsed data to the dictionary
            water_usage_data[date_time] = float(consumption)

    sample_data = list(water_usage_data.items())[: min(5, len(water_usage_data))]
    logger.debug(f"Parsed data (sample): {sample_data}")

    return water_usage_data


def save_as_csv(excel_content: bytes, start_date: str, outdir: Path) -> Path:
    """Save xls data from SFPUC to csv directly.

    Args:
        excel_content (bytes): The content of the Excel file.
        start_date (str): The start date in MM/DD/YYYY format.
        outdir (Path): The directory to save the CSV file.

    Returns:
        Path: The path to the saved CSV file.

    """
    decoded_csv = excel_content.decode("utf-8")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_filename = outdir / f"HourlyUsage_{start_date.replace('/', '-')}.csv"

    with csv_filename.open("w") as f:
        decoded_csv = decoded_csv.replace("\t", ",")
        lines = decoded_csv.split("\n")
        header = "DateTime,Consumption\n"
        f.write(header)

        for line in lines[1:]:
            if line.strip():
                hour, consumption = line.split(",")
                date_time_str = f"{start_date} {hour}"
                date_time = datetime.strptime(date_time_str, "%m/%d/%Y %I %p")
                f.write(f"{date_time},{consumption}\n")

    return csv_filename
