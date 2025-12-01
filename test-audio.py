#!/usr/bin/env python
from pathlib import Path as OsPath
from youtube_dl_scraper.utils.audio_extractor import extract_mp3
from youtube_dl_scraper import YouTube

# def download_youtube_audio(youtube_url, output_path):
#     try:
#         # yt_dlp_cmd = 'yt-dlp.exe' if os.name == 'nt' else 'yt-dlp'
#         yt_dlp_cmd = 'yt-dlp'
#         subprocess.run([
#             yt_dlp_cmd,
#             '-x', '--audio-format', 'mp3',
#             '-o', output_path,
#             youtube_url
#         ], check=True)
#         print(f"Audio downloaded and saved as {output_path}")
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"An error occurred: {e}")    
#         return False

        
youtube = YouTube(video_scraper_name='savetube')
url = "https://www.youtube.com/watch?v=hB3KkRcIEoc"
video = youtube.scrape_video(url)

# # download mp3 by yt_dlp command
# filename = f"{video.title_slug}.mp3"
# path = OsPath(video.download_path)
# path.mkdir(parents=True, exist_ok=True)

# file_path = path / filename
# final_audio_filepath = file_path.as_posix()

# print(final_audio_filepath)

# result = download_youtube_audio(url, final_audio_filepath)
# if not result:
# try:
#     audio_file = video.streams.get_higher_bitrate().download()
#     print(audio_file)
# except Exception as e:
    # print(f"audio download failed, try video instead.${e}")
# 下载视频然后用ffmpeg抽取音频
video_file = video.streams.get_highest_resolution().download()
print(video_file)
# 下载完成，用ffmpeg抽取mp3音频
video_path = OsPath(video_file)
# 获取文件后缀（带点号）
file_ext = video_path.suffix
# 构建新的音频文件名
if file_ext:
    # 使用with_suffix方法更安全地替换后缀
    new_audio_filename = str(video_path.with_suffix('.mp3'))
else:
    # 如果原文件没有后缀，直接添加.mp3
    new_audio_filename = str(video_path) + '.mp3'

extract_mp3(video_file, new_audio_filename)

# else:
#     print(f"okkkkkk")
#     audio_file = final_audio_filepath
