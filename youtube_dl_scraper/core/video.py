from .stream_array import StreamArray
from .caption_array import CaptionArray
from .stream import VideoStream, AudioStream
from youtube_dl_scraper.utils.format_time import format_duration
from youtube_dl_scraper.utils import title_to_slug


class Video:
    """Data class representing a video with streams and captions."""

    def __init__(self, video_data: dict, download_path: str):
        """
        Initialize the Video object with data and set up basic properties.

        Args:
            video_data (dict): A dictionary containing video metadata such as ID, title, etc.
            download_path (str): The directory path where the video and its streams will be saved.
        """
        self.raw_video_data = video_data
        self.download_path = download_path
        self.id = video_data.get("id")
        self.title = video_data.get("title")
        self.title_slug = video_data.get("title_slug") or title_to_slug(self.title)
        self.watch_url = video_data.get("watch_url")
        self.duration = video_data.get("duration")
        self.formatted_duration = video_data.get(
            "formatted_duration"
        ) or format_duration(self.duration)
        self.fduration = self.formatted_duration  # short hand to formatted_duration
        self.thumbnail = video_data.get("thumbnail")
        self._get_captions = None
        self.__custom_props = video_data.get("custom_props", {})

    def __getattr__(self, key):
        if key in self.__custom_props:
            return self.__custom_props[key]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{key}'"
        )

    def __parse_streams(self, streams: dict) -> StreamArray:
        """
        Parse video and audio streams from the given stream data.

        Args:
            streams (dict): A dictionary containing stream data with keys 'video' and 'audio'.

        Returns:
            StreamArray: An object containing parsed video and audio streams.
        """
        video_streams = streams.get("video", [])
        video_api = streams.get("video_api", {})
        audio_streams = streams.get("audio", [])
        audio_api = streams.get("audio_api", {})

        streams = StreamArray(video_api=video_api, audio_api=audio_api)

        # Adding video streams
        for stream in video_streams:
            vid = VideoStream(
                stream, file_name=self.title_slug, download_path=self.download_path
            )
            url = vid.get_url()
            # print(f"video url is ${url}")
            if url and url[:4] == 'http':
                streams.add_stream(vid)

        # Adding audio streams
        for stream in audio_streams:
            aud = AudioStream(
                stream, file_name=self.title_slug, download_path=self.download_path
            )
            url = aud.get_url()
            # print(f"audio url is ${url}")
            if url and url[:4] == 'http':            
                streams.add_stream(aud)

        return streams

    @property
    def streams(self) -> StreamArray:
        """
        Property that retrieves the streams for the video.

        Returns:
            StreamArray: The parsed video and audio streams.

        Raises:
            KeyError: If the "streams" key is missing in the raw video data.
        """
        streams = self.raw_video_data.get("streams")
        if callable(streams):
            streams = streams()
        if not streams:
            raise KeyError("No streams found in video data")
        return self.__parse_streams(streams)

    @property
    def captions(self) -> CaptionArray:
        """
        Property that retrieves the captions for the video.

        Returns:
            CaptionArray: The captions for the video.

        Raises:
            NotImplementedError: If captions are not available.
        """
        if not self._get_captions:
            raise NotImplementedError("Captions property is not implemented")
        return self._get_captions()
