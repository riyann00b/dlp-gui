import logging
import os
import platform
from typing import List, Dict, Union


class ActivityLogger:
    def __init__(self, app_name: str = "dlp-gui", log_file: str = None):
        self.app_name = app_name
        self.log_file = log_file or self._get_default_log_path()
        self.setup_logger()

    def _get_default_log_path(self) -> str:
        """Return default log file path depending on OS."""
        system = platform.system()

        if system == "Windows":
            base_dir = os.path.join(os.getenv("APPDATA", ""), self.app_name, "logs")
        elif system == "Darwin":  # macOS
            base_dir = os.path.expanduser(f"~/Library/Logs/{self.app_name}")
        else:  # Linux & others
            base_dir = os.path.expanduser(f"~/.cache/{self.app_name}/logs")

        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, f"{self.app_name}.log")

    def setup_logger(self) -> None:
        """Setup logging configuration."""
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # Console handler (optional, for debugging)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_activity(self, message: str, level: str = "info") -> None:
        """Log activity with timestamp and level."""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)

    def log_download_start(self, url: str, format_type: str, output_path: str) -> None:
        """Log download start event with metadata."""
        self.log_activity(
            f"DOWNLOAD_START - URL: {url}, Format: {format_type}, OutputPath: {output_path}"
        )

    def log_download_complete(
        self, url: str, success: bool, file_path: Union[str, None] = None
    ) -> None:
        """Log download completion event."""
        status = "SUCCESS" if success else "FAILED"
        message = f"DOWNLOAD_COMPLETE - {status} - URL: {url}"
        if file_path:
            message += f", FilePath: {file_path}"
        self.log_activity(message)

    def log_blocked_content(self, url: str, reason: str = "Content filter") -> None:
        """Log blocked content attempt."""
        self.log_activity(
            f"BLOCKED_CONTENT - URL: {url}, Reason: {reason}", level="warning"
        )

    def log_error(self, error_message: str, context: str = "", file_path: str = "") -> None:
        """Log error events with optional context and file path."""
        message = f"ERROR - {error_message}"
        if context:
            message += f" - Context: {context}"
        if file_path:
            message += f" - FilePath: {file_path}"
        self.log_activity(message, level="error")

    def get_recent_logs(self, lines: int = 50) -> List[str]:
        """Get recent log entries."""
        try:
            if not os.path.exists(self.log_file):
                return ["No logs found."]

            with open(self.log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except Exception as e:
            return [f"Error reading logs: {e}"]

    def clear_logs(self) -> bool:
        """Clear all log entries."""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            self.setup_logger()  # Reinitialize logger
            self.log_activity("Log file cleared")
            return True
        except Exception as e:
            self.log_activity(f"Failed to clear logs: {e}", level="error")
            return False

    def get_log_stats(self) -> Dict[str, int]:
        """Get statistics about logged activities."""
        try:
            if not os.path.exists(self.log_file):
                return {"total_entries": 0, "downloads": 0, "errors": 0, "blocked": 0}

            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            return {
                "total_entries": len(lines),
                "downloads": sum("DOWNLOAD_START" in line for line in lines),
                "errors": sum("ERROR" in line for line in lines),
                "blocked": sum("BLOCKED_CONTENT" in line for line in lines),
            }

        except Exception as e:
            self.log_activity(f"Error getting log stats: {e}", level="error")
            return {"error": str(e)}
