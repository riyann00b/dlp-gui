import os
import yt_dlp
from typing import Callable, Optional, Dict, List, Any
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
            # Fallback: ensure errors in hook don't crash downloader
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
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Download video/audio using yt-dlp with given configuration.

        Args:
            url (str): URL to download.
            output_path (str): Output directory path.
            config_options (dict): yt-dlp configuration options.
            progress_callback (function, optional): Callback for progress updates.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not url or not isinstance(url, str):
            self.logger.log_activity("Invalid URL provided for download.")
            return False

        try:
            ydl_opts = config_options.copy()

            # Ensure output directory exists
            os.makedirs(output_path, exist_ok=True)

            # Configure output template
            outtmpl = ydl_opts.get("outtmpl", "%(title)s.%(ext)s")
            ydl_opts["outtmpl"] = os.path.join(output_path, outtmpl)

            # Add progress hook if provided
            if progress_callback:
                ydl_opts["progress_hooks"] = [DownloadProgressHook(progress_callback)]

            # Log activity
            self.logger.log_activity(f"Download started: {url}")
            self.logger.log_activity(f"yt-dlp options: {config_options}")

            # Start download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.logger.log_activity(f"Download completed successfully: {url}")
            return True

        except yt_dlp.utils.DownloadError as e:
            msg = f"Download error: {e}"
            self.logger.log_activity(msg)
            if progress_callback:
                progress_callback(msg)
            return False

        except Exception as e:
            msg = f"Unexpected error: {e}"
            self.logger.log_activity(msg)
            if progress_callback:
                progress_callback(msg)
            return False

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get video information without downloading.

        Args:
            url (str): URL to analyze.

        Returns:
            dict | None: Video information or None if error.
        """
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

        """Add a file to the Recent Downloads list"""
        item = QListWidgetItem(file_path)
        self.recent_list.insertItem(0, item)  # newest on top

        # keep only last 10 entries
        if self.recent_list.count() > 10:
            self.recent_list.takeItem(self.recent_list.count() - 1)

    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """
        Get list of available formats for a URL.

        Args:
            url (str): URL to check.

        Returns:
            list: List of format dictionaries.
        """
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("formats", [])

        except Exception as e:
            self.logger.log_activity(f"Format extraction error: {e}")
            return []
