"""Download hourly usage data from the SFPUC website."""

from datetime import datetime, timedelta
import logging
import re

import requests

from .utils import get_hidden_fields_from_page, parse_download_data

_LOGGER = logging.getLogger(__name__)


def get_available_date_range(session: requests.Session) -> tuple[datetime, datetime]:
    """Get available date range for downloading hourly usage data.

    Args:
        session (requests.Session): SFPUC login session.

    Returns:
        tuple: start_date (datetime), end_date (datetime)

    """
    hourly_usage_url = "https://myaccount-water.sfpuc.org/USE_HOURLY.aspx"

    # Use your session to make the request
    response = session.get(hourly_usage_url)

    # Ensure the request was successful
    if response.status_code == 200:
        response_text = response.text
        # Use regex to extract startDate and endDate from the JavaScript
        start_date_match = re.search(r'"startDate":"([^"]+)"', response_text)
        end_date_match = re.search(r'"endDate":"([^"]+)"', response_text)

        if start_date_match and end_date_match:
            # Extract the date strings
            start_date_str = start_date_match.group(1)
            end_date_str = end_date_match.group(1)

            # Convert the strings into datetime objects
            start_date = datetime.strptime(start_date_str, "%a, %d %b %Y %H:%M:%S GMT")
            end_date = datetime.strptime(end_date_str, "%a, %d %b %Y %H:%M:%S GMT")
            _LOGGER.info("Available date range: %s to %s", start_date, end_date)
            return start_date, end_date

        _LOGGER.warning("Start date or End date not found in the response")
        return None, None
    _LOGGER.error("Failed to fetch the page, status code: %s", response.status_code)
    raise ValueError("Failed to fetch the Hourly Usage page.")


def download_hourly_usage(session: requests.Session, start_date: str) -> dict:
    """Download the Excel file for the given date and return parsed water usage data.

    Args:
        session (requests.Session): SFPUC login session.
        start_date (str): Date in the format 'mm/dd/yyyy' to download the data for.

    Returns:
        dict: Parsed water usage data with timestamps (datetime) and consumption (float).

    """
    try:
        hourly_usage_url = "https://myaccount-water.sfpuc.org/USE_HOURLY.aspx"
        response = session.get(hourly_usage_url)

        hidden_fields = get_hidden_fields_from_page(response.text)

        data = {
            "__VIEWSTATE": hidden_fields["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden_fields["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden_fields["__EVENTVALIDATION"],
            "img_EXCEL_DOWNLOAD_IMAGE.x": "13",
            "img_EXCEL_DOWNLOAD_IMAGE.y": "9",
            "SD": start_date,
            "dl_UOM": "GALLONS",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://myaccount-water.sfpuc.org/USE_HOURLY.aspx",
            "User-Agent": "Mozilla/5.0",
        }

        response = session.post(
            hourly_usage_url, data=data, headers=headers, allow_redirects=False
        )

        if "Location" in response.headers:
            download_url = (
                "https://myaccount-water.sfpuc.org" + response.headers["Location"]
            )
            excel_response = session.get(download_url, headers=headers)

            if (
                excel_response.status_code == 200
                and "application/vnd.ms-excel"
                in excel_response.headers.get("Content-Type", "")
            ):
                _LOGGER.info("Successfully accessed download data for %s", start_date)

                # Stream directly for processing
                # data = io.BytesIO(excel_response.content)

                return parse_download_data(excel_response.content, start_date)
            _LOGGER.error(
                "Unexpected content type: %s",
                excel_response.headers.get("Content-Type", ""),
            )
    except requests.RequestException as e:
        _LOGGER.error(
            "HTTP error occurred while downloading the Excel file for %s: %s",
            start_date,
            e,
        )
        return {}
    except ValueError as e:
        _LOGGER.error(
            "Value error occurred while processing the Excel file for %s: %s",
            start_date,
            e,
        )
        return {}
    except KeyError as e:
        _LOGGER.error(
            "Key error occurred while processing hidden fields for %s: %s",
            start_date,
            e,
        )
        return {}


def download_usage_for_multiple_days(
    session: requests.Session, start_date: str, end_date: str
) -> dict:
    """Download the hourly usage Excel files for a range of dates and return parsed data.

    Args:
        session (requests.Session): The session object for making HTTP requests.
        start_date (str): The start date in the format 'mm/dd/yyyy'.
        end_date (str): The end date in the format 'mm/dd/yyyy'.

    Returns:
        dict: A dictionary containing parsed data for the date range.

    """
    # Parse the input start and end dates
    try:
        start_date = datetime.strptime(start_date, "%m/%d/%Y")
        end_date = datetime.strptime(end_date, "%m/%d/%Y")
    except ValueError as e:
        _LOGGER.error("Date format error: %s", e)
        return {}

    # Get the available date range from the website
    available_start_date, available_end_date = get_available_date_range(session)

    # Check if the requested start date is before the available start date
    if start_date < available_start_date:
        _LOGGER.warning(
            "Start date %s is earlier than the available start date %s. Adjusting to the earliest available date",
            start_date.strftime("%m/%d/%Y"),
            available_start_date.strftime("%m/%d/%Y"),
        )
        start_date = available_start_date

    # Check if the requested end date is after the available end date
    if end_date > available_end_date:
        _LOGGER.warning(
            "End date %s is later than the available end date %s. Adjusting to the latest available date",
            end_date.strftime("%m/%d/%Y"),
            available_end_date.strftime("%m/%d/%Y"),
        )
        end_date = available_end_date

    # If the start date is after the end date after adjustment, return an empty result
    if start_date > end_date:
        _LOGGER.warning(
            "Start date %s is later than the end date %s. No data to download",
            start_date.strftime("%m/%d/%Y"),
            end_date.strftime("%m/%d/%Y"),
        )
        return {}

    # Initialize dictionary to store all data
    all_data = {}

    # Iterate through each day in the range
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%m/%d/%Y")

        # Download the usage data for the current day
        day_data = download_hourly_usage(session, date_str)

        if day_data:
            # Combine daily data into the all_data dictionary
            all_data.update(day_data)
        else:
            _LOGGER.warning("No data found for %s. Skipping", date_str)

        # Move to the next day
        current_date += timedelta(days=1)

    # Return all the data collected
    return all_data
