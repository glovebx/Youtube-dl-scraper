#!/usr/bin/env python
from youtube_dl_scraper import YouTube
youtube = YouTube()
video = youtube.scrape_video("https://www.youtube.com/watch?v=Co18rgGig0w")
audio_file = video.streams.get_higher_bitrate().download()
print(audio_file)