import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent
from youtube_dl_scraper.core.base_scraper import BaseScraper
from youtube_dl_scraper.core.exceptions import (
    ScraperExecutionError,
    VideoNotFoundError,
)


class Mp3Youtube(BaseScraper):

    # meta data
    __name__ = "Mp3Youtube"
    __type__ = "video"
    __host__ = "mp3youtube.cc"

    video_qualities = ["144", "360", "480", "720", "1080"]
    audio_qualities = ["128", "320"]

    headers = {
        "Accept": "*/*",
        "Origin": "cov.mp3youtube.cc",
        "Referer": "cov.mp3youtube.cc",
    }

    ua_generator = UserAgent()

    def __init__(self, download_path: str):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        retries = Retry(
            total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def get_key(self):
        user_agent = self.ua_generator.random
        self.session.headers.update({"User-Agent": user_agent})
        response = self.session.get(f"https://api.{self.__host__}/v2/sanity/key")
        data = response.json()
        if response.status_code != 200:
            raise ScraperExecutionError(
                self.__name__,
                f"Mp3Youtube Error fetching key: invalid response code {response.status_code}{', Error Message: ' + data['errorMsg'] + '.' if data['errorMsg'] else '.'}",
            )

        self.session.headers.update(data)
        return data["key"]

    def get_video_info(self, url: str) -> dict:
        payload = {"link": url}
        response = self.session.post(
            f"https://api.{self.__host__}/v2/getVideoInfo", data=payload
        )
        data = response.json()
        if response.status_code != 200:
            raise VideoNotFoundError(
                f"Mp3Youtube Error fetching video data: invalid status code {response.status_code}{', Error Message: ' + data['errorMsg'] + '.' if data['errorMsg'] else '.'}"
            )

        return data

    def convert(self, payload: dict):
        payload = {"format": "mp4", **payload}

        print(payload)

        response = self.session.post(
            f"https://api.{self.__host__}/v2/converter", data=payload
        )

        data = response.json()

        return data

    def scrape(self, url: str) -> dict:
        """Scrape video information."""
        key = self.get_key()
        if not (key or isinstance(key, str)):
            raise ScraperExecutionError(
                self.__name__, "Mp3Youtube Error Occured While Scraping, Invalid key gotten."
            )

        data = self.get_video_info(url)

        return self.parse_video_data(data)

    def parse_video_data(self, data: dict) -> dict:
        """Parse video data into a structured format."""
        video_data = {
            "id": data["videoId"],
            "title": data["title"],
            "watch_url": f"https://m.youtube.com/watch?v={data['videoId']}",
            "thumbnail": data["thumbnail"],
            "duration": data[
                "duration"
            ],  # TODO: duration not working add duration and other missig data globaly using youtube api.
            "formatted_duration": data["videoTime"],
        }

        def get_url(data):
            if data.get("error"):
                raise ScraperExecutionError(
                    f"Mp3Youtube Conversion Error {': ' + data['errorMsg'] + '.' if data['errorMsg'] else '.'}"
                )

            return data["url"]

        # Parse stream data
        streams = {"video": [], "audio": []}

        # Parse video streams
        for quality in self.video_qualities:
            streams["video"].append(
                {
                    "quality": int(quality),
                    "label": f"{quality}p",
                    "args": [
                        {
                            "link": video_data["watch_url"],
                            "videoQuality": quality,
                            "vCodec": "h264",
                        }
                    ],
                    "get_url": (lambda payload: get_url(self.convert(payload))),
                }
            )

        # Parse audio streams
        for quality in self.audio_qualities:
            streams["audio"].append(
                {
                    "quality": int(quality),
                    "label": f"{quality}kbps",
                    "args": [
                        {
                            "link": video_data["watch_url"],
                            "format": "mp3",
                            "audioBitrate": quality,
                        }
                    ],
                    "get_url": (lambda payload: get_url(self.convert(payload))),
                }
            )

        video_data["streams"] = streams
        return video_data
