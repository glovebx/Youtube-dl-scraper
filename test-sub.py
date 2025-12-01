#!/usr/bin/env python
from youtube_dl_scraper import YouTube
youtube = YouTube(caption_scraper_name='downsub')
captions = youtube.scrape_captions("https://www.youtube.com/watch?v=qOarZGXuxZ8")
print(captions)
# print(captions.subtitles)

# 定义语言代码的尝试顺序
lang_priority = ['a.en', 'en', 'en-US', 'a.ja', 'ja', 'ja-JP']

caption = None
for lang_code in lang_priority:
    caption = captions.get_captions_by_lang_code(lang_code)
    if caption:
        break  # 一旦找到可用的字幕，立即退出循环            

print(caption)
print(caption.txt())
print(caption.raw2file())