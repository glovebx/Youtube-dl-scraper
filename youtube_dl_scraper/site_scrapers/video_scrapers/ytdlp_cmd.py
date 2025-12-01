import re
import subprocess
import os
from youtube_dl_scraper.core.base_scraper import BaseScraper
from youtube_dl_scraper.core.exceptions import (
    YouTubeDLScraperError,
    ScraperExecutionError,
    VideoNotFoundError,
)

# 暂时废弃，不是标准的Scraper
class YtdlpCmd(BaseScraper):
    # Meta data
    __name__ = "YtdlpCmd"
    __type__ = "video"
    __host__ = "localhost"

    def __init__(self, download_path: str):
        self.download_path = download_path
        pass

    def scrape(self, url: str) -> dict:
        """Scrape video information."""

        output_path = '.'
        result = self.download_youtube_audio(url, output_path)
        if not result:
            raise VideoNotFoundError("No data found for the requested video")

        video_data = {
            "audio_file": output_path,
        }
        return video_data
\
    def download_youtube_audio(self, youtube_url, output_path):
        try:
            # yt_dlp_cmd = 'yt-dlp.exe' if os.name == 'nt' else 'yt-dlp'
            yt_dlp_cmd = 'yt-dlp'
            subprocess.run([
                yt_dlp_cmd,
                '-x', '--audio-format', 'mp3',
                '-o', output_path,
                youtube_url
            ], check=True)
            print(f"Audio downloaded and saved as {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"An error occurred: {e}")    
            return False
