"""Login to the SFPUC water account system and return an authenticated session."""

import logging
import time

import requests

logger = logging.getLogger(__name__)


def login(username: str, password: str) -> requests.Session:
    """Log into the SFPUC water account system and returns an authenticated session."""

    login_page_url = "https://myaccount-water.sfpuc.org/~~~QUFBQUFBV1pwbU05OHZldjhIZG5YMU1GUTVYNmp5MllUVE9Ga21wU2prWi9wTGlZZlE9PQ==ZZZ"
    login_post_url = "https://myaccount-water.sfpuc.org/~~~QUFBQUFBVU9uVGUrWmFxM2NuN2ZDbDM5Uy93cXhpbnNuakpTTUVlck01NFA1TXhtNnc9PQ==ZZZ"
    final_page_url = "https://myaccount-water.sfpuc.org/MY_ACCOUNT_RSF.aspx"

    session = requests.Session()

    try:
        initial_response = session.get(login_page_url)
        # Extract hidden fields
        viewstate = initial_response.text.split('id="__VIEWSTATE" value="')[1].split(
            '"'
        )[0]
        eventvalidation = initial_response.text.split('id="__EVENTVALIDATION" value="')[
            1
        ].split('"')[0]
        viewstategenerator = initial_response.text.split(
            'id="__VIEWSTATEGENERATOR" value="'
        )[1].split('"')[0]

        # Prepare POST data for login
        login_data = {
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategenerator,
            "__EVENTVALIDATION": eventvalidation,
            "tb_USER_ID": username,
            "tb_USER_PSWD": password,
            "btn_SIGN_IN_BUTTON": "Sign in",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://myaccount-water.sfpuc.org",
        }

        time.sleep(0.1)
        login_response = session.post(
            login_post_url, data=login_data, headers=headers, allow_redirects=False
        )

        if "Location" in login_response.headers:
            redirect_url = (
                "https://myaccount-water.sfpuc.org" + login_response.headers["Location"]
            )
            session.get(redirect_url, headers=headers)

        final_response = session.get(final_page_url, headers=headers)

        if final_response.status_code == 200 and ("Welcome" in final_response.text):
            logger.info("Successfully logged into SFPUC water account")
            return session
        logger.error(f"Login failed: {final_response.status_code}")
        logger.debug(f"Response: {final_response.text}")
        return None

    except Exception as e:
        logger.error(f"Error during login: {e}")
        return None
