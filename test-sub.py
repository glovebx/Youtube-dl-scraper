#!/usr/bin/env python
from youtube_dl_scraper import YouTube
youtube = YouTube(caption_scraper_name='notegpt')
captions = youtube.scrape_captions("https://www.youtube.com/watch?v=Co18rgGig0w")
print(captions)
# print(captions.subtitles)

caption = captions.get_captions_by_lang_code('a.en')
if not caption:
    caption = captions.get_captions_by_lang_code('en')
    if not caption:
        caption = captions.get_captions_by_lang_code('en-US')

print(caption)
print(caption.txt())
print(caption.raw2file())