from pathlib import Path
from typing import Union, Optional, Callable
import requests
import fleep
from tqdm import tqdm
from .exceptions import FileExistsError
from youtube_dl_scraper.utils.filename_extractor import get_filename_from_cd


def file_exists(filename: str, directory: Union[str, Path]) -> Optional[str]:
    """
    Check if a file with the given name (without extension) exists in the directory.

    Args:
        filename (str): The stem (name without extension) of the file to search for.
        directory (Union[str, Path]): The path to the directory to search in. Can be a string or a Path object.

    Returns:
        Optional[str]: The full path to the file if it exists, otherwise None.

    Raises:
        ValueError: If the provided directory path is invalid or does not exist.
    """
    dir_path = Path(directory)

    if not dir_path.is_dir():
        raise ValueError(f"The provided path '{directory}' is not a valid directory.")

    for file in dir_path.iterdir():
        if file.is_file() and file.stem == filename:
            return str(file)

    return None


class Stream:
    """
    A base class for handling streams and downloading files.

    Attributes:
        file_name (str): The name of the file to download.
        download_dir (str): The directory where the file will be downloaded.
        size (dict): A dictionary containing size details (width and height).
        get_url (Callable): A callable to retrieve the stream URL.

    Methods:
        download: Downloads the file and handles renaming based on its type.
    """

    def __init__(self, stream_data: dict, download_dir: str = "", file_name: str = ""):
        """
        Initialize a Stream object.

        Args:
            stream_data (dict): Metadata about the stream.
            download_dir (str, optional): Directory to download the file. Defaults to "download".
            file_name (str, optional): Name of the file to be downloaded. Defaults to "download".
        """
        self._stream_data = stream_data
        self.file_name = file_name or "download"
        self.download_dir = download_dir or "download"
        self._get_url = stream_data.get("get_url")
        self.get_url_args = stream_data.get("args")
        self.get_url = lambda: self._get_url(*self.get_url_args)
        self.size = {
            "width": stream_data.get("width"),
            "height": stream_data.get("height"),
        }

    def download(
        self,
        file_name: str = "",
        skip_existent: bool = False,
        error_on_existent: bool = False,
        download_dir: str = "",
        on_complete: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Download the stream and optionally rename it based on its type.

        Args:
            file_name (str, optional): Name of the file to be downloaded. Defaults to the initialized file name.
            skip_existent (bool, optional): Skip download if the file already exists. Defaults to False.
            error_on_existent (bool, optional): Raise an error if the file already exists. Defaults to False.
            download_dir (str, optional): Directory to download the file. Defaults to the initialized directory.
            on_complete (Callable, optional): A callback function to run after download. Receives the file path as an argument.

        Returns:
            str: The path to the downloaded file.

        Raises:
            FileExistsError: If the file exists and `error_on_existent` is True.
            RuntimeError: If the download fails.
        """
        file_name = file_name or self.file_name
        download_path = download_dir or self.download_dir
        path = Path(download_path)
        path.mkdir(parents=True, exist_ok=True)

        if full_name := file_exists(file_name, path):
            if skip_existent:
                print("File exists")
                return full_name
            if error_on_existent:
                raise FileExistsError(full_name, path)                        
        try:
            url = self.get_url()
            print(f"audio download starting...${url}")
            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                file_ext = Path(file_name).suffix
                if not file_ext:
                    cd_filename = get_filename_from_cd(
                            response.headers.get("content-disposition") or ""
                        )                    
                    if cd_filename:
                        file_ext = Path(cd_filename).suffix
                    else:
                        if isinstance(self, VideoStream):
                            file_ext = '.mp4'
                        else:
                            file_ext = '.mp3'
                file_path = path / (file_name + file_ext)
                with file_path.open("wb") as file, tqdm(
                    desc=f"Downloading {file_name + file_ext}",
                    total=total_size if total_size > 0 else None,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    ncols=80,
                ) as progress_bar:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
                            progress_bar.update(len(chunk))

                print(f"Download completed: {file_name}")
                if not file_ext:
                    with file_path.open("rb") as file:
                        file_type = fleep.get(file.read(128))
                        if file_type.extension:
                            print("Renaming file")
                            extension = file_type.extension[0]
                            new_file_path = file_path.with_suffix("." + extension)
                            file_path.rename(new_file_path)
                            if on_complete:
                                on_complete(new_file_path)
                            return str(new_file_path)
                if on_complete:
                    on_complete(file_path)
                return str(file_path)

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download {file_name}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred: {e}") from e


class VideoStream(Stream):
    """
    A class for handling video streams.

    Attributes:
        resolution_label (str): The resolution label of the video (e.g., "1080p").
        resolution_value (str): The numeric resolution quality.
        has_audio (bool): Indicates if the video has audio.
        frame_rate (int): The frame rate of the video.
        is_hdr (bool): Indicates if the video supports HDR.
    """

    __type__ = "video"
    is_video = True
    is_audio = False

    def __init__(self, stream_data: dict, download_path: str = "", file_name: str = ""):
        """
        Initialize a VideoStream object.

        Args:
            stream_data (dict): Metadata about the video stream.
            download_path (str, optional): Directory to download the file. Defaults to "".
            file_name (str, optional): Name of the file to be downloaded. Defaults to "".
        """
        super().__init__(stream_data, download_path, file_name)
        self.resolution_label = stream_data.get("label")
        self.resolution = self.resolution_label  # alias for resolution_label
        self.resolution_value = stream_data.get("quality")
        self.has_audio = stream_data.get("has_audio", True)
        self.frame_rate = stream_data.get("frame_rate", 30)
        self.is_hdr = stream_data.get("hdr", False)
        self.fps = self.frame_rate
        self.file_name += f"-{self.resolution_label}-{self.frame_rate}fps{'-HDR' if self.is_hdr else ''}{'-noaud' if not self.has_audio else ''}"

    def __str__(self) -> str:
        return f"(video {self.resolution} {self.frame_rate}fps)"

    def __repr__(self) -> str:
        return f"(video {self.resolution} {self.frame_rate}fps is_hdr={self.is_hdr} has_audio={self.has_audio})"


class AudioStream(Stream):
    """
    A class for handling audio streams.

    Attributes:
        abr_label (str): The audio bitrate label (e.g., "128kbps").
        abr (str): The numeric audio quality (alias for bitrate).
    """

    __type__ = "audio"
    is_video = False
    is_audio = True

    def __init__(self, stream_data: dict, download_path: str = "", file_name: str = ""):
        """
        Initialize an AudioStream object.

        Args:
            stream_data (dict): Metadata about the audio stream.
            download_path (str, optional): Directory to download the file. Defaults to "".
            file_name (str, optional): Name of the file to be downloaded. Defaults to "".
        """
        super().__init__(stream_data, download_path, file_name)
        self.abr_label = stream_data.get("label")
        self.abr = stream_data.get("quality")  # alias for quality
        self.file_name += f"-{self.abr_label}"

    def __str__(self) -> str:
        return f"(audio {self.abr})"

    def __repr__(self) -> str:
        return f"(audio {self.abr})"
