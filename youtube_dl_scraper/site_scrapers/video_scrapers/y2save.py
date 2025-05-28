import json
import math
import re
import random
import requests
from fake_useragent import UserAgent
from youtube_dl_scraper.core.base_scraper import BaseScraper
from youtube_dl_scraper.core.exceptions import (
    YouTubeDLScraperError,
    ScraperExecutionError,
    VideoNotFoundError,
)


class Y2Save(BaseScraper):
    # Meta data
    __name__ = "Y2Save"
    __type__ = "video"
    __host__ = "y2save.com"

    video_qualities = ["360P", "480P", "720P", "1080P"]
    audio_qualities = ["128kbps"]

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://y2save.com",
        "referer": "https://y2save.com/id",
        "x-requested-with": "XMLHttpRequest",
    }

    # ua_generator = UserAgent(platforms="pc")
    ua_generator = UserAgent(browsers=["chrome"])

    def __init__(self, download_path: str):
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_csrf_token(self):
        """Fetch CSRF token and cookies from the site."""
        url = f"https://{self.__host__}/id"
        self.session.headers.update({"User-Agent": self.ua_generator.random})
        response = self.session.get(url)

        if response.status_code != 200:
            raise ScraperExecutionError(
                self.__name__,
                f"Y2Save Error fetching CSRF token: invalid response code: {response.status_code}",
            )

        csrf_token = response.text.split('name="csrf-token" content="')[1].split('"')[0]
        return csrf_token

    def scrape(self, url: str) -> dict:
        """Scrape video information."""
        csrf_token = self.get_csrf_token()
        payload = f"_token={csrf_token}&query={url}"
        response = self.session.post(f"https://{self.__host__}/search", data=payload)

        if response.status_code != 200:
            raise ScraperExecutionError(
                self.__name__,
                f"Y2Save Error occurred fetching video data: invalid response code: {response.status_code}",
            )

        data = response.json()
        if data.get("status") != "ok":
            raise VideoNotFoundError("No data found for the requested video")

        return self.parse_video_data(data["data"])

    def convert(self, payload: dict) -> str:
        """Convert video or audio using the provided vid and key."""
        csrf_token = self.get_csrf_token()
        # payload = f"_token={csrf_token}&{payload}"
        payload = {"_token": csrf_token, **payload}
        response = self.session.post(
            f"https://{self.__host__}/searchConvert", data=payload
        )

        if response.status_code != 200:
            raise ScraperExecutionError(
                self.__name__,
                f"Y2Save Error occurred during conversion: invalid response code: {response.status_code}",
            )

        data = response.json()
        if data.get("c_status") == "FAILED":
            raise ScraperExecutionError(self.__name__, "Y2Save Conversion failed")
        return data["dlink"]

    def parse_video_data(self, data: dict) -> dict:
        """Parse video data into a structured format."""
        video_data = {
            "id": data["vid"],
            "title": data["title"],
            "watch_url": f"https://m.youtube.com/watch?v={data['vid']}",
            "thumbnail": data["thumbnail"],
            "duration": data["vduration"],
        }

        # Parse stream data
        streams = {"video": [], "audio": []}

        # Parse video streams
        for stream in data["convert_links"].get("video", []):
            quality = stream["quality"]
            if quality != "auto":
                cleaned_quality = re.sub("p|P", "", quality)
                quality = int(cleaned_quality or 0) or None
            else:
                quality = -1
            streams["video"].append(
                {
                    "quality": quality,
                    "label": stream["quality"].lower(),
                    "key": stream["key"],
                    "args": [{"vid": data["vid"], "key": stream["key"]}],
                    "get_url": (lambda payload: self.convert(payload)),
                }
            )

        # Parse audio streams
        for stream in data["convert_links"].get("audio", []):
            streams["audio"].append(
                {
                    "quality": int(stream.get("quality", None).replace("kbps", ""))
                    or 0,
                    "label": stream["quality"].lower(),
                    "key": stream["key"],
                    "args": [{"vid": data["vid"], "key": stream["key"]}],
                    "get_url": (lambda payload: self.convert(payload)),
                }
            )

        video_data["streams"] = streams
        return video_data
