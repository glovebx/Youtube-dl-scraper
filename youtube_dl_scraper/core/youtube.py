import asyncio
from typing import Optional
from .scraper_manager import ScraperManager
from .exceptions import ScraperExecutionError
from .video import Video
from .caption_array import CaptionArray


class YouTube:
    """A class for scraping YouTube videos and captions using specified scrapers."""

    def __init__(
        self,
        video_scraper_name: Optional[str] = "savetube",
        caption_scraper_name: Optional[str] = "downsub",
        download_path: Optional[str] = "downloads",
    ):
        """
        Initialize the YouTube scraper with the specified video and caption scrapers.

        Args:
            video_scraper_name (Optional[str]): The name of the video scraper (default is "savetube").
            caption_scraper_name (Optional[str]): The name of the caption scraper (default is "downsub").
            download_path (Optional[str]): The directory path where videos and captions will be saved (default is "downloads").
        """
        from . import Manager

        self.manager = Manager
        self.download_path = download_path or "/downloads"

        # Initialize video scraper
        video_scraper_class = self.manager.get_scraper_class(
            "video", video_scraper_name
        )
        self.video_scraper = video_scraper_class(self.download_path)
        self.video_scraper_name = video_scraper_name

        # Initialize caption scraper
        caption_scraper_class = self.manager.get_scraper_class(
            "caption", caption_scraper_name
        )
        self.caption_scraper = caption_scraper_class(self.download_path)
        self.caption_scraper_name = caption_scraper_name

    def scrape_video(self, url: str) -> Video:
        """
        Synchronously scrape video data from the given URL.

        Args:
            url (str): The URL of the video to scrape.

        Returns:
            Video: A Video object containing the scraped video data.

        Raises:
            ScraperExecutionError: If an error occurs while scraping the video.
        """
        try:
            video_data = self.video_scraper.scrape(url)
            vid = Video(video_data, self.download_path)
            vid._get_captions = lambda: self.scrape_captions(url)
            return vid
        except Exception as e:
            raise ScraperExecutionError(self.video_scraper_name, str(e))

    async def async_scrape_video(self, url: str) -> Video:
        """
        Asynchronously scrape video data from the given URL.

        Args:
            url (str): The URL of the video to scrape.

        Returns:
            Video: A Video object containing the scraped video data.

        Raises:
            ScraperExecutionError: If an error occurs while scraping the video.
        """
        try:
            video_data = await self.video_scraper.async_scrape(url)
            vid = Video(video_data, self.download_path)
            return vid
        except Exception as e:
            raise ScraperExecutionError(self.video_scraper_name, str(e))

    def scrape_captions(self, url: str) -> CaptionArray:
        """
        Synchronously scrape captions from the given URL.

        Args:
            url (str): The URL of the video for which to scrape captions.

        Returns:
            CaptionArray: A CaptionArray object containing the scraped captions.

        Raises:
            ScraperExecutionError: If an error occurs while scraping captions.
        """
        try:
            caption_data = self.caption_scraper.scrape_captions(url)
            captions = CaptionArray(caption_data, self.download_path)
            return captions
        except Exception as e:
            raise ScraperExecutionError(self.caption_scraper_name, str(e))

    async def async_scrape_captions(self, url: str) -> CaptionArray:
        """
        Asynchronously scrape captions from the given URL.

        Args:
            url (str): The URL of the video for which to scrape captions.

        Returns:
            CaptionArray: A CaptionArray object containing the scraped captions.

        Raises:
            ScraperExecutionError: If an error occurs while scraping captions.
        """
        try:
            caption_data = await self.caption_scraper.async_scrape(url)
            captions = CaptionArray(caption_data, self.download_path)
            return captions
        except Exception as e:
            raise ScraperExecutionError(self.caption_scraper_name, str(e))
