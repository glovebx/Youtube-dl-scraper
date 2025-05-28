import requests
from requests.adapters import HTTPAdapter
# from requests.packages.urllib3.util.retry import Retry
from urllib3.util.retry import Retry
from youtube_dl_scraper.core.exceptions import PlaywrightError
from typing import Dict, Optional


class Playwright:
    """
    A class that interacts with the Playwright service to execute code remotely.

    Attributes:
        available_languages (list): A list of supported programming languages for remote code execution.
        server (str): The URL endpoint for the Playwright service.
    """

    available_languages = ["javascript", "python", "java", "csharp"]
    server = "https://try.playwright.tech/service/control/run"

    @staticmethod
    def run(code: str, language: str = "python") -> Dict[str, Optional[str]]:
        """
        Executes a code snippet remotely using Playwright's cloud service.

        Args:
            code (str): The code to be executed remotely.
            language (str): The programming language in which the code is written. Default is "python".

        Returns:
            dict: A dictionary containing the execution result with keys such as `status_code`,
                  `success`, `error`, and `output`.

        Raises:
            ValueError: If the provided language is not supported.
            PlaywrightError: If an error occurs during the HTTP request or code execution.
        """

        if language.lower() not in Playwright.available_languages:
            raise ValueError(
                f"Language not supported. Supported languages are {Playwright.available_languages}"
            )

        headers = {
            "authority": "try.playwright.tech",
            "accept": "*/*",
            "content-type": "application/json",
            "origin": "https://try.playwright.tech",
            "referer": f"https://try.playwright.tech/?l={language.lower() if language else 'playwright-test'}",
            "user-agent": "Postify/1.0.0",
        }

        # Prepare the payload for the POST request
        data = {"code": code, "language": language}
        session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))

        try:
            response = session.post(Playwright.server, headers=headers, json=data)
            response.raise_for_status()
            out = response.json()
            out["status_code"] = response.status_code
            return out
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
            data = response.json()
            raise PlaywrightError(
                f"HTTP error occurred: {err}",
                response.status_code,
                data.get("success", ""),
                data.get("error", ""),
                data.get("output", ""),
            )
        except ValueError as e:
            print("Failed to decode JSON response.")
            raise PlaywrightError(repr(e))
