import os
import yt_dlp
from typing import Callable, Optional, Dict, List, Any, Tuple
from Core.logger import ActivityLogger


class DownloadProgressHook:
    """Handles yt-dlp progress events and forwards them to a callback."""

    def __init__(self, progress_callback: Callable[[str], None]):
        self.progress_callback = progress_callback

    def __call__(self, d: Dict[str, Any]) -> None:
        try:
            status = d.get("status")

            if status == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)

                if total_bytes:
                    percent = (downloaded / total_bytes) * 100
                    speed = d.get("speed", 0)
                    speed_str = f" at {speed/1024/1024:.1f} MB/s" if speed else ""
                    eta = d.get("eta")
                    eta_str = f", ETA: {eta}s" if eta else ""
                    msg = f"Downloading: {percent:.1f}%{speed_str}{eta_str}"
                else:
                    msg = f"Downloading... ({downloaded/1024/1024:.2f} MB)"

                self.progress_callback(msg)

            elif status == "finished":
                filename = d.get("filename", "unknown file")
                self.progress_callback(f"Downloaded: {filename}")

            elif status == "error":
                error_msg = d.get("error", "Unknown error")
                self.progress_callback(f"Error: {error_msg}")

        except Exception as e:
            self.progress_callback(f"Progress hook error: {e}")


class Downloader:
    """Downloader class to handle video/audio downloads using yt-dlp."""

    def __init__(self) -> None:
        self.logger = ActivityLogger()

    def download(
        self,
        url: str,
        output_path: str,
        config_options: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Download video/audio using yt-dlp with given configuration.

        Args:
            url (str): URL to download.
            output_path (str): Output directory path.
            config_options (dict): yt-dlp configuration options.
            progress_callback (function, optional): Callback for progress updates.

        Returns:
            (bool, list[str]): Success flag and list of downloaded file paths.
        """
        if not url or not isinstance(url, str):
            self.logger.log_activity("Invalid URL provided for download.")
            return False, []

        try:
            ydl_opts = config_options.copy()
            os.makedirs(output_path, exist_ok=True)

            outtmpl = ydl_opts.get("outtmpl", "%(title)s.%(ext)s")
            ydl_opts["outtmpl"] = os.path.join(output_path, outtmpl)

            if progress_callback:
                ydl_opts["progress_hooks"] = [DownloadProgressHook(progress_callback)]

            self.logger.log_activity(f"Download started: {url}")
            self.logger.log_activity(f"yt-dlp options: {config_options}")

            file_paths: List[str] = []
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # Single video
                if "entries" not in info:
                    file_paths.append(ydl.prepare_filename(info))
                else:  # Playlist
                    for entry in info["entries"]:
                        if entry:
                            file_paths.append(ydl.prepare_filename(entry))

            self.logger.log_activity(f"Download completed successfully: {url}")
            return True, file_paths

        except yt_dlp.utils.DownloadError as e:
            msg = f"Download error: {e}"
            self.logger.log_activity(msg)
            if progress_callback:
                progress_callback(msg)
            return False, []

        except Exception as e:
            msg = f"Unexpected error: {e}"
            self.logger.log_activity(msg)
            if progress_callback:
                progress_callback(msg)
            return False, []

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown"),
                    "view_count": info.get("view_count", 0),
                    "formats": len(info.get("formats", [])),
                    "is_playlist": "entries" in info,
                }
        except Exception as e:
            self.logger.log_activity(f"Info extraction error: {e}")
            return None

    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("formats", [])
        except Exception as e:
            self.logger.log_activity(f"Format extraction error: {e}")
            return []
