# config.py
import copy
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class YTDLPConfig:
    """
    yt-dlp configuration manager for generating options
    based on user-selected formats and preferences.
    """

    # Preset format labels (used in UI / main.py)
    FORMAT_PRESETS = {
        "BEST_VIDEO_AUDIO": "Best Quality (Video + Audio)",
        "BEST_VIDEO_ONLY": "Best Video Only",
        "BEST_AUDIO_ONLY": "Best Audio Only",
        "VIDEO_720P": "720p Video + Audio",
        "VIDEO_480P": "480p Video + Audio",
        "MP3_AUDIO": "MP3 Audio Only",
        "CUSTOM": "Custom",
    }

    def __init__(self) -> None:
        self.base_options: Dict[str, Any] = {
            "outtmpl": "%(title)s.%(ext)s",
            "ignoreerrors": True,
            "no_warnings": False,
        }

    # ----------------------
    # Main Format Configs
    # ----------------------

    def get_config(self, format_type: str) -> Dict[str, Any]:
        """
        Return yt-dlp configuration based on format selection.

        Args:
            format_type (str): One of the preset format labels.

        Returns:
            dict: yt-dlp options.
        """
        config = copy.deepcopy(self.base_options)

        if format_type == self.FORMAT_PRESETS["BEST_VIDEO_AUDIO"]:
            config.update(self._get_h264_video_config("best[height<=1080]"))

        elif format_type == self.FORMAT_PRESETS["BEST_VIDEO_ONLY"]:
            config.update(self._get_h264_video_config("bestvideo[height<=1080]"))

        elif format_type == self.FORMAT_PRESETS["BEST_AUDIO_ONLY"]:
            config.update(self._get_audio_config(codec="mp3", quality="192"))

        elif format_type == self.FORMAT_PRESETS["VIDEO_720P"]:
            config.update(self._get_h264_video_config("best[height<=720]"))

        elif format_type == self.FORMAT_PRESETS["VIDEO_480P"]:
            config.update(self._get_h264_video_config("best[height<=480]"))

        elif format_type == self.FORMAT_PRESETS["MP3_AUDIO"]:
            config.update(self._get_audio_config(codec="mp3", quality="320"))

        elif format_type == self.FORMAT_PRESETS["CUSTOM"]:
            config.update(self._get_h264_video_config("best"))

        else:
            logger.warning(f"Unknown format type: {format_type}, falling back to 'best'")
            config.update(self._get_h264_video_config("best"))

        return config
    def _get_h264_video_config(self, format_string: str) -> Dict[str, Any]:
        """Internal helper for video configs with H.264 encoding."""
        return {
            "format": format_string,
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
        }

    # ----------------------
    # Extended Configs
    # ----------------------

    def get_playlist_config(self) -> Dict[str, Any]:
        """Configuration for playlist downloads."""
        return {
            "outtmpl": "%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
            "noplaylist": False,
        }

    def get_subtitle_config(self, langs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Configuration for subtitle downloads."""
        return {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs or ["en"],
            "subtitlesformat": "srt",
        }

    def get_audio_only_config(self, codec: str = "mp3", quality: str = "192") -> Dict[str, Any]:
        """Configuration for audio-only downloads."""
        return self._get_audio_config(codec, quality)

    def get_video_only_config(self, quality: str = "best") -> Dict[str, Any]:
        """Configuration for video-only downloads."""
        return {
            "format": f"bestvideo[height<={quality}]" if quality.isdigit() else "bestvideo",
            "merge_output_format": "mp4",
        }

    def get_custom_format_config(self, format_string: str) -> Dict[str, Any]:
        """Configuration for custom yt-dlp format strings."""
        return {"format": format_string, "merge_output_format": "mp4"}

    # ----------------------
    # Internal Helpers
    # ----------------------

    def _get_audio_config(self, codec: str, quality: str) -> Dict[str, Any]:
        """Internal helper for audio-only configs."""
        return {
            "format": "bestaudio",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": codec,
                    "preferredquality": quality,
                }
            ],
        }
