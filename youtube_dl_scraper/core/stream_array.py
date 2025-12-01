from typing import Optional, List, Dict, Callable, Union
from .stream import Stream, VideoStream, AudioStream


class StreamArray:
    """
    A utility class to manage and manipulate a collection of video and audio streams.
    """

    def __init__(
        self, **kwargs: Union[List[Stream], Dict[str, Union[Callable, List[Stream]]]]
    ):
        """
        Initialize the StreamArray object.

        Args:
            streams (List[Stream], optional): A list of initial streams to add.
            video_api (Callable, optional): A callable for video stream APIs (reserved for future use).
            audio_api (Callable, optional): A callable for audio stream APIs (reserved for future use).
        """
        self._streams = []
        self._resolutions = []

        if kwargs.get("streams"):
            self._streams.extend(kwargs["streams"])

        # TODO: use the api_functions to get custom streams
        self._vid_stream_api = kwargs.get("video_api")
        self._aud_stream_api = kwargs.get("audio_api")

    @property
    def streams(self) -> tuple[Stream, ...]:
        """
        Return all streams, sorted by resolution for videos and bitrate for audio.

        Returns:
            tuple[Stream, ...]: Sorted tuple of streams.
        """
        return tuple(
            sorted(
                self._streams,
                key=(lambda s: s.resolution_value or 0 if s.is_video else s.abr),
                reverse=True,
            )
        )

    @property
    def resolutions(self) -> tuple[int, ...]:
        """
        Get all unique video resolutions in the stream collection.

        Returns:
            tuple[int, ...]: Tuple of video resolutions.
        """
        resolutions = [
            stream.resolution_value for stream in self.streams if stream.is_video
        ]
        return tuple(resolutions)

    @property
    def bitrates(self) -> tuple[int, ...]:
        """
        Get all unique audio bitrates in the stream collection.

        Returns:
            tuple[int, ...]: Tuple of audio bitrates.
        """
        bitrates = [stream.abr for stream in self.streams if stream.is_audio]
        return tuple(bitrates)

    @property
    def frame_rates(self) -> tuple[int, ...]:
        """
        Get all unique frame rates from video streams.

        Returns:
            tuple[int, ...]: Tuple of frame rates.
        """
        frame_rates = list(
            set([stream.fps for stream in self.streams if stream.is_video])
        )
        return tuple(frame_rates)

    @property
    def available_qualities(self) -> dict[str, tuple[int, ...]]:
        """
        Get available video and audio qualities.

        Returns:
            dict[str, tuple[int, ...]]: A dictionary containing video resolutions and audio bitrates.
        """
        return {"video": self.resolutions, "audio": self.bitrates}

    def add_stream(self, *streams: Stream) -> None:
        """
        Add one or more streams to the collection.

        Args:
            *streams (Stream): Streams to add.
        """
        self._streams.extend(streams)

    def _get_audio(self) -> list:
        aud_streams = filter((lambda stream: stream.is_audio), self.streams)
        ordered_by_abr = sorted(
            aud_streams,
            key=(lambda stream: stream.abr if stream.abr else 0),
            reverse=True,
        )

        return list(ordered_by_abr)

    def _get_video(self) -> list:
        video_streams = filter((lambda stream: stream.is_video), self.streams)
        ordered_by_res = sorted(
            video_streams,
            key=(lambda stream: int(stream.resolution_value) if stream.is_video else 0),
            reverse=True,
        )
        if len(ordered_by_res) > 0:
            ordered_by_frame_rate = sorted(
                ordered_by_res, key=lambda stream: int(stream.fps), reverse=True
            )
            ordered_by_hdr = sorted(
                ordered_by_frame_rate, key=(lambda stream: stream.is_hdr), reverse=True
            )
            return list(ordered_by_hdr)

        return []

    def get_highest_bitrate(self) -> Optional[AudioStream]:
        """
        Get the audio stream with the highest bitrate.

        Returns:
            Optional[AudioStream]: The highest bitrate audio stream.
        """
        ordered_by_abr = self._get_audio()
        if ordered_by_abr:
            return ordered_by_abr[0]
        
    def get_higher_bitrate(self) -> Optional[AudioStream]:
        """
        Get the audio stream with the highest bitrate.

        Returns:
            Optional[AudioStream]: The highest bitrate audio stream.
        """
        ordered_by_abr = self._get_audio()
        if ordered_by_abr:
            if len(ordered_by_abr) > 1:
                return ordered_by_abr[1]
            return ordered_by_abr[0]

    def get_highest_resolution(self) -> Optional[VideoStream]:
        """
        Get the video stream with the highest resolution.

        Returns:
            Optional[VideoStream]: The highest resolution video stream.
        """
        video_streams = self._get_video()
        if video_streams:
            return video_streams[0]
        
    def get_lowest_resolution(self) -> Optional[VideoStream]:
        """
        Get the video stream with the lowest resolution.

        Returns:
            Optional[VideoStream]: The lowest resolution video stream.
        """
        video_streams = self._get_video()
        if video_streams:
            return video_streams[-1]

    def get_audio_streams(self):
        """
        Get a new StreamArray containing only audio streams.

        Returns:
            Self: A StreamArray with audio streams.
        """
        audio_streams = self._get_audio()
        return StreamArray(streams=audio_streams)

    def get_video_streams(self):
        """
        Get a new StreamArray containing only video streams.

        Returns:
            Self: A StreamArray with video streams.
        """
        video_streams = self._get_video()
        return StreamArray(streams=video_streams)

    def filter(self, **kwargs: Union[str, int, bool]):
        """
        Filter streams based on attributes.

        Args:
            **kwargs (Union[str, int, bool]): Attribute-value pairs to filter by.

        Returns:
            Self: A StreamArray with the filtered streams.
        """
        reverse = kwargs.pop("reverse", None)
        if reverse is not None and not isinstance(reverse, bool):
            raise ValueError("Reverse keyword argument must be of type bool")

        filtered = [
            stream
            for stream in self.streams
            if all(getattr(stream, key, None) == value for key, value in kwargs.items())
        ]
        return StreamArray(streams=filtered)

    def order_by(self, key: str, reverse: bool = False):
        """
        Order streams by a specific attribute.

        Args:
            key (str): The attribute to order by.
            reverse (bool): Whether to reverse the order.

        Returns:
            Self: A StreamArray with ordered streams.
        """
        if not all(hasattr(stream, key) for stream in self.streams):
            raise ValueError(f"Key '{key}' not found in all streams.")
        return StreamArray(
            streams=sorted(
                self.streams,
                key=lambda stream: getattr(stream, key),
                reverse=(not reverse),
            )
        )

    def first(self) -> Optional[Stream]:
        """
        Get the first stream in the collection.

        Returns:
            Optional[Stream]: The first stream, or None if empty.
        """
        if self.streams:
            return self.streams[0]

    def last(self) -> Optional[Stream]:
        """
        Get the last stream in the collection.

        Returns:
            Optional[Stream]: The last stream, or None if empty.
        """
        if self.streams:
            return self.streams[-1]

    def __len__(self) -> int:
        """
        Get the number of streams.

        Returns:
            int: The number of streams.
        """
        return len(self.streams)

    def __getitem__(self, index: Union[int, slice]) -> Stream:
        """
        Access a stream by its index or sliced stream array by its slice.

        Args:
            index (Union[int, slice]):
                index (int): The index of the stream.
                slice (slice): The slice of the streams.

        Returns:
            outputs (Union[Stream, StreamArray])
                Stream: The stream at the given index.
                StreamArray: The stream array from the slice.
        """
        try:
            if isinstance(index, slice):
                return StreamArray(streams=list(self.streams[index]))
            elif isinstance(index, int):
                return self.streams[index]
            else:
                raise TypeError("Invalid argument type.")
        except IndexError:
            raise IndexError(f"No stream found at index: {index}")

    def __str__(self) -> str:
        """
        Get a string representation of the streams.

        Returns:
            str: String representation of the streams.
        """
        return str(self.streams)

    def __iter__(self):
        """
        Initialize iteration over the streams.

        Returns:
            Self: The StreamArray object.
        """
        self.i = 0
        return self

    def __next__(self) -> Stream:
        """
        Get the next stream during iteration.

        Returns:
            Stream: The next stream.

        Raises:
            StopIteration: If no more streams are available.
        """
        if self.i < len(self.streams):
            item = self.streams[self.i]
            self.i += 1
            return item
        else:
            raise StopIteration
