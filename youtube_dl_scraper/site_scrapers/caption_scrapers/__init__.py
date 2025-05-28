# youtube_dl_scraper/site_scrapers/caption_scrapers/__init__.py
# from youtube_dl_scraper.core.base_scraoer import BaseScraper
from youtube_dl_scraper.utils.registration import register_scrapers
from .downsub import DownSub
from .notegpt import NoteGpt


def register(*scraper_objs):
    """Register caption scrapers."""
    register_scrapers(scrapers, *scraper_objs)


# Register caption scrapers
scrapers = {}
caption_scrapers = scrapers

# register scrapers
register(DownSub)
register(NoteGpt)
