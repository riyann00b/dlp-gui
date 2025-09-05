import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition, QTimer
from Core.downloader import Downloader


class DownloadStatus(Enum):
    """Download status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    """Data class for download progress information."""
    status: DownloadStatus
    progress: float = 0.0
    speed: float = 0.0
    eta: Optional[int] = None
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    filename: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "filename": self.filename,
            "error_message": self.error_message
        }


class DownloadThread(QThread):
    """Enhanced download thread with pause/resume, cancellation, and detailed progress."""

    # Enhanced signals
    progress_updated = pyqtSignal(DownloadProgress)
    download_started = pyqtSignal(str)  # URL
    download_completed = pyqtSignal(bool, str, list)  # success, message, file_paths
    download_cancelled = pyqtSignal()
    error_occurred = pyqtSignal(str, str)  # error_type, error_message

    def __init__(self, url: str, output_path: str, config_options: Dict[str, Any]):
        super().__init__()

        self.url = url
        self.output_path = output_path
        self.config_options = config_options.copy()

        self.downloader = Downloader()
        self.download_id = f"dl_{int(time.time())}"

        # Thread control
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        self._is_paused = False
        self._is_cancelled = False
        self._should_stop = False

        # Progress tracking
        self._current_progress = DownloadProgress(DownloadStatus.PENDING)
        self._start_time = None
        self._last_update_time = 0
        self._update_interval = 0.5  # Update UI every 500ms

        # File tracking
        self._downloaded_files: List[str] = []
        self._temp_files: List[str] = []

    def run(self) -> None:
        """Main thread execution with comprehensive error handling."""
        self._start_time = time.time()
        self._current_progress.status = DownloadStatus.DOWNLOADING
        self.download_started.emit(self.url)

        try:
            # Validate inputs
            self._validate_inputs()

            # Setup output directory
            self._setup_output_directory()

            # Configure downloader with progress callback
            self.config_options["progress_hooks"] = [self._progress_callback]

            # Start download
            success, file_paths = self.downloader.download(
                self.url,
                self.output_path,
                self.config_options,
                progress_callback=self._progress_message_callback
            )

            if self._is_cancelled:
                self._cleanup_temp_files()
                self._current_progress.status = DownloadStatus.CANCELLED
                self.download_cancelled.emit()
                return

            if success and file_paths:
                self._downloaded_files = file_paths
                self._current_progress.status = DownloadStatus.COMPLETED
                self._current_progress.progress = 100.0
                self.progress_updated.emit(self._current_progress)

                completion_message = self._get_completion_message(file_paths)
                self.download_completed.emit(True, completion_message, file_paths)
            else:
                self._current_progress.status = DownloadStatus.FAILED
                self._current_progress.error_message = "Download failed - no files were downloaded"
                self.progress_updated.emit(self._current_progress)
                self.download_completed.emit(False, "Download failed", [])

        except DownloadValidationError as e:
            self._handle_error("validation", str(e))
        except DownloadNetworkError as e:
            self._handle_error("network", str(e))
        except DownloadStorageError as e:
            self._handle_error("storage", str(e))
        except Exception as e:
            self._handle_error("unknown", f"Unexpected error: {str(e)}")

    def pause(self) -> None:
        """Pause the download (if supported by the underlying downloader)."""
        with QMutex(self._mutex):
            if self._current_progress.status == DownloadStatus.DOWNLOADING:
                self._is_paused = True
                self._current_progress.status = DownloadStatus.PAUSED
                self.progress_updated.emit(self._current_progress)

    def resume(self) -> None:
        """Resume a paused download."""
        with QMutex(self._mutex):
            if self._current_progress.status == DownloadStatus.PAUSED:
                self._is_paused = False
                self._current_progress.status = DownloadStatus.DOWNLOADING
                self.progress_updated.emit(self._current_progress)
                self._wait_condition.wakeAll()

    def cancel(self) -> None:
        """Cancel the download and cleanup."""
        with QMutex(self._mutex):
            self._is_cancelled = True
            self._should_stop = True
            if self._is_paused:
                self._wait_condition.wakeAll()

    def get_download_info(self) -> Dict[str, Any]:
        """Get current download information."""
        elapsed_time = time.time() - self._start_time if self._start_time else 0

        return {
            "download_id": self.download_id,
            "url": self.url,
            "output_path": self.output_path,
            "status": self._current_progress.status.value,
            "progress": self._current_progress.to_dict(),
            "elapsed_time": elapsed_time,
            "downloaded_files": self._downloaded_files.copy()
        }

    def _validate_inputs(self) -> None:
        """Validate download inputs."""
        if not self.url or not isinstance(self.url, str):
            raise DownloadValidationError("Invalid URL provided")

        if not self.output_path:
            raise DownloadValidationError("Output path not specified")

        # Check if output path is writable
        output_dir = Path(self.output_path)
        if output_dir.exists() and not os.access(output_dir, os.W_OK):
            raise DownloadStorageError(f"Output directory is not writable: {output_dir}")

    def _setup_output_directory(self) -> None:
        """Setup and validate output directory."""
        try:
            output_dir = Path(self.output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise DownloadStorageError(f"Failed to create output directory: {e}")

    def _progress_callback(self, progress_data: Dict[str, Any]) -> None:
        """Enhanced progress callback for yt-dlp."""
        current_time = time.time()

        # Throttle updates to avoid overwhelming the UI
        if current_time - self._last_update_time < self._update_interval:
            return

        try:
            status = progress_data.get("status")

            if self._is_cancelled:
                return

            # Handle pause state
            if self._is_paused:
                with QMutex(self._mutex):
                    self._wait_condition.wait(self._mutex)
                if self._is_cancelled:
                    return

            if status == "downloading":
                self._handle_downloading_progress(progress_data)
            elif status == "finished":
                self._handle_finished_progress(progress_data)
            elif status == "error":
                error_msg = progress_data.get("error", "Unknown download error")
                raise DownloadNetworkError(error_msg)

            self._last_update_time = current_time

        except Exception as e:
            self._handle_error("progress", f"Progress callback error: {e}")

    def _handle_downloading_progress(self, data: Dict[str, Any]) -> None:
        """Handle downloading progress updates."""
        total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate")
        downloaded_bytes = data.get("downloaded_bytes", 0)
        speed = data.get("speed", 0)
        eta = data.get("eta")
        filename = data.get("filename", "")

        progress_percent = 0.0
        if total_bytes and total_bytes > 0:
            progress_percent = min(100.0, (downloaded_bytes / total_bytes) * 100)

        self._current_progress = DownloadProgress(
            status=DownloadStatus.DOWNLOADING,
            progress=progress_percent,
            speed=speed or 0,
            eta=eta,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            filename=os.path.basename(filename) if filename else ""
        )

        self.progress_updated.emit(self._current_progress)

    def _handle_finished_progress(self, data: Dict[str, Any]) -> None:
        """Handle finished file progress."""
        filename = data.get("filename", "")
        if filename and filename not in self._downloaded_files:
            self._downloaded_files.append(filename)

        # Update progress to show file completion
        self._current_progress.filename = os.path.basename(filename) if filename else ""
        self._current_progress.progress = 100.0
        self.progress_updated.emit(self._current_progress)

    def _progress_message_callback(self, message: str) -> None:
        """Handle text progress messages from downloader."""
        # This can be used for additional logging or status updates
        pass

    def _get_completion_message(self, file_paths: List[str]) -> str:
        """Generate a completion message based on downloaded files."""
        file_count = len(file_paths)
        if file_count == 1:
            return f"Successfully downloaded: {os.path.basename(file_paths[0])}"
        else:
            return f"Successfully downloaded {file_count} files"

    def _handle_error(self, error_type: str, error_message: str) -> None:
        """Handle errors with cleanup."""
        self._current_progress.status = DownloadStatus.FAILED
        self._current_progress.error_message = error_message
        self.progress_updated.emit(self._current_progress)

        self.error_occurred.emit(error_type, error_message)
        self.download_completed.emit(False, error_message, [])

        # Cleanup on error
        self._cleanup_temp_files()

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files on cancellation or error."""
        try:
            for temp_file in self._temp_files:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()
        except OSError:
            pass  # Best effort cleanup

    def terminate_download(self) -> None:
        """Forcefully terminate the download thread."""
        self.cancel()
        if self.isRunning():
            self.wait(5000)  # Wait up to 5 seconds
            if self.isRunning():
                self.terminate()  # Force terminate if needed
                self.wait()


class DownloadManager(QThread):
    """Manager for multiple concurrent downloads with queue support."""

    # Add missing signals
    download_added = pyqtSignal(str)  # download_id
    download_removed = pyqtSignal(str)  # download_id
    download_started = pyqtSignal(str)  # url
    download_completed = pyqtSignal(bool, str, list)  # success, message, file_paths
    download_cancelled = pyqtSignal(str)  # download_id
    download_failed = pyqtSignal(str, str)  # download_id, error_message
    download_progress = pyqtSignal(str, dict)  # download_id, progress_info
    queue_status_changed = pyqtSignal(dict)  # queue statistics
    all_downloads_completed = pyqtSignal()
    manager_status_changed = pyqtSignal(str)  # status message
    download_error = pyqtSignal(str, str)  # download_id, error_message
    download_finished = pyqtSignal(str, bool, str, list)  # download_id, success, message, file_paths

    def __init__(self, max_concurrent_downloads: int = 3):
        super().__init__()

        self.max_concurrent_downloads = max_concurrent_downloads
        self._active_downloads: Dict[str, DownloadThread] = {}
        self._download_queue: List[DownloadThread] = []
        self._completed_downloads: List[str] = []

        self._mutex = QMutex()
        self._is_running = False

        # Statistics timer
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._emit_queue_stats)
        self._stats_timer.start(2000)  # Update every 2 seconds

    def add_download(self, url: str, output_path: str, config_options: Dict[str, Any]) -> str:
        """Add a new download to the queue."""
        with QMutexLocker(self._mutex):
            download_thread = DownloadThread(url, output_path, config_options)

            # Connect all signals
            download_thread.download_started.connect(self._on_download_thread_started)
            download_thread.download_completed.connect(self._on_download_completed)
            download_thread.download_cancelled.connect(self._on_download_cancelled)
            download_thread.error_occurred.connect(self._on_download_error)
            download_thread.progress_updated.connect(self._on_progress_updated)

            self._download_queue.append(download_thread)
            self.download_added.emit(download_thread.download_id)

            if not self._is_running:
                self._is_running = True
                self.start()

            return download_thread.download_id

    def remove_download(self, download_id: str) -> bool:
        """Remove a download from queue or cancel if active."""
        with QMutex(self._mutex):
            # Check active downloads
            if download_id in self._active_downloads:
                download_thread = self._active_downloads[download_id]
                download_thread.cancel()
                return True

            # Check queue
            for i, download_thread in enumerate(self._download_queue):
                if download_thread.download_id == download_id:
                    self._download_queue.pop(i)
                    self.download_removed.emit(download_id)
                    return True

            return False

    def pause_download(self, download_id: str) -> bool:
        """Pause an active download."""
        if download_id in self._active_downloads:
            self._active_downloads[download_id].pause()
            return True
        return False

    def resume_download(self, download_id: str) -> bool:
        """Resume a paused download."""
        if download_id in self._active_downloads:
            self._active_downloads[download_id].resume()
            return True
        return False

    def pause_all(self) -> int:
        """Pause all active downloads. Returns number of downloads paused."""
        paused_count = 0
        for download_thread in self._active_downloads.values():
            if download_thread._current_progress.status == DownloadStatus.DOWNLOADING:
                download_thread.pause()
                paused_count += 1
        return paused_count

    def resume_all(self) -> int:
        """Resume all paused downloads. Returns number of downloads resumed."""
        resumed_count = 0
        for download_thread in self._active_downloads.values():
            if download_thread._current_progress.status == DownloadStatus.PAUSED:
                download_thread.resume()
                resumed_count += 1
        return resumed_count

    def cancel_all(self) -> int:
        """Cancel all active downloads and clear queue. Returns number of downloads cancelled."""
        cancelled_count = 0

        # Cancel active downloads
        for download_thread in self._active_downloads.values():
            download_thread.cancel()
            cancelled_count += 1

        # Clear queue
        cancelled_count += len(self._download_queue)
        self._download_queue.clear()

        return cancelled_count

    def get_download_by_id(self, download_id: str) -> Optional[DownloadThread]:
        """Get download thread by ID."""
        # Check active downloads
        if download_id in self._active_downloads:
            return self._active_downloads[download_id]

        # Check queue
        for download_thread in self._download_queue:
            if download_thread.download_id == download_id:
                return download_thread

        return None

    def get_active_downloads(self) -> List[DownloadThread]:
        """Get list of currently active download threads."""
        return list(self._active_downloads.values())

    def get_queued_downloads(self) -> List[DownloadThread]:
        """Get list of queued download threads."""
        return self._download_queue.copy()

    def get_download_count(self) -> Dict[str, int]:
        """Get count of downloads by status."""
        return {
            "active": len(self._active_downloads),
            "queued": len(self._download_queue),
            "completed": len(self._completed_downloads)
        }

    def get_all_downloads_info(self) -> List[Dict[str, Any]]:
        """Get information about all downloads (active and queued)."""
        downloads_info = []

        # Active downloads
        for download_thread in self._active_downloads.values():
            downloads_info.append(download_thread.get_download_info())

        # Queued downloads
        for download_thread in self._download_queue:
            info = download_thread.get_download_info()
            info["status"] = "queued"
            downloads_info.append(info)

        return downloads_info

    def clear_completed(self) -> None:
        """Clear completed downloads from tracking."""
        with QMutex(self._mutex):
            self._completed_downloads.clear()

    def set_max_concurrent_downloads(self, max_downloads: int) -> None:
        """Set maximum number of concurrent downloads."""
        if max_downloads > 0:
            self.max_concurrent_downloads = max_downloads

    def is_active(self) -> bool:
        """Check if download manager is currently active."""
        return self._is_running

    def get_status(self) -> str:
        """Get current manager status."""
        if not self._is_running:
            return "idle"
        elif self._active_downloads:
            return "downloading"
        elif self._download_queue:
            return "queued"
        else:
            return "finishing"

    def run(self) -> None:
        """Main download manager loop."""
        self.manager_status_changed.emit("started")

        while self._is_running:
            self._process_download_queue()
            self.msleep(1000)  # Check every second

        self.manager_status_changed.emit("stopped")

    def _process_download_queue(self) -> None:
        """Process the download queue and start new downloads."""
        with QMutexLocker(self._mutex):
            # Clean up completed downloads
            completed_ids = []
            for download_id, download_thread in list(self._active_downloads.items()):
                if not download_thread.isRunning():
                    completed_ids.append(download_id)

            for download_id in completed_ids:
                del self._active_downloads[download_id]
                self._completed_downloads.append(download_id)

            # Start new downloads if slots available
            available_slots = self.max_concurrent_downloads - len(self._active_downloads)
            for _ in range(min(available_slots, len(self._download_queue))):
                if self._download_queue:
                    download_thread = self._download_queue.pop(0)
                    self._active_downloads[download_thread.download_id] = download_thread
                    download_thread.start()

            # Check if all downloads are completed
            if not self._active_downloads and not self._download_queue and self._completed_downloads:
                self.all_downloads_completed.emit()

            # Stop manager if no active downloads or queue
            if not self._active_downloads and not self._download_queue:
                self._is_running = False

    def _on_download_thread_started(self, url: str) -> None:
        """Handle individual download thread started."""
        self.download_started.emit(url)

    def _on_download_completed(self, success: bool, message: str, file_paths: List[str]) -> None:
        """Handle download completion."""
        sender_thread = self.sender()
        if hasattr(sender_thread, 'download_id'):
            download_id = sender_thread.download_id
            self.download_completed.emit(success, message, file_paths)
            self.download_finished.emit(download_id, success, message, file_paths)

    def _on_download_cancelled(self) -> None:
        """Handle download cancellation."""
        sender_thread = self.sender()
        if hasattr(sender_thread, 'download_id'):
            download_id = sender_thread.download_id
            self.download_cancelled.emit(download_id)

    def _on_download_error(self, error_type: str, error_message: str) -> None:
        """Handle download errors."""
        sender_thread = self.sender()
        if hasattr(sender_thread, 'download_id'):
            download_id = sender_thread.download_id
            self.download_failed.emit(download_id, error_message)
            self.download_error.emit(download_id, error_message)

    def _on_progress_updated(self, progress: DownloadProgress) -> None:
        """Handle progress updates from download threads."""
        sender_thread = self.sender()
        if hasattr(sender_thread, 'download_id'):
            download_id = sender_thread.download_id
            progress_info = progress.to_dict()
            self.download_progress.emit(download_id, progress_info)

    def _emit_queue_stats(self) -> None:
        """Emit current queue statistics."""
        stats = {
            "active_downloads": len(self._active_downloads),
            "queued_downloads": len(self._download_queue),
            "completed_downloads": len(self._completed_downloads),
            "max_concurrent": self.max_concurrent_downloads,
            "total_downloads": len(self._active_downloads) + len(self._download_queue) + len(self._completed_downloads)
        }
        self.queue_status_changed.emit(stats)

    def stop_manager(self) -> None:
        """Stop the download manager and all active downloads."""
        with QMutex(self._mutex):
            self._is_running = False

            # Cancel all active downloads
            for download_thread in self._active_downloads.values():
                download_thread.cancel()

            # Clear queue
            self._download_queue.clear()

        # Wait for manager thread to finish
        if self.isRunning():
            self.wait(5000)

        self._stats_timer.stop()
        self.manager_status_changed.emit("stopped")

# Custom exceptions for better error handling
class DownloadError(Exception):
    """Base exception for download errors."""
    pass


class DownloadValidationError(DownloadError):
    """Exception for input validation errors."""
    pass


class DownloadNetworkError(DownloadError):
    """Exception for network-related errors."""
    pass


class DownloadStorageError(DownloadError):
    """Exception for storage-related errors."""
    pass


# Utility functions for download management
def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable format."""
    if bytes_value == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(bytes_value)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def format_speed(bytes_per_second: float) -> str:
    """Format download speed into human readable format."""
    if bytes_per_second <= 0:
        return "0 B/s"

    return f"{format_bytes(int(bytes_per_second))}/s"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds <= 0:
        return "Unknown"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"
