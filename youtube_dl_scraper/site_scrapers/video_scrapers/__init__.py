# youtube_dl_scraper/site_scrapers/video_scrapers/__init__.py
# from youtube_dl_scraper.core.base_scraoer import BaseScraper
from youtube_dl_scraper.utils.registration import register_scrapers
from .savetube import SaveTube
from .mp3youtube import Mp3Youtube
from .y2save import Y2Save
# from .ytdlp_cmd import YtdlpCmd


def register(*scraper_objs):
    """Register video scrapers"""
    register_scrapers(scrapers, *scraper_objs)


# Register video scrapers
scrapers = {}
video_scrapers = scrapers

# register scrapers
register(SaveTube)
register(Mp3Youtube)
register(Y2Save)
# register(YtdlpCmd)
