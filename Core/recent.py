import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import threading
from dataclasses import dataclass


@dataclass
class RecentItem:
    """Data class for recent download items with metadata."""
    file_path: str
    download_time: str
    url: str = ""
    file_size: int = 0
    format_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "download_time": self.download_time,
            "url": self.url,
            "file_size": self.file_size,
            "format_type": self.format_type
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecentItem':
        return cls(
            file_path=data.get("file_path", ""),
            download_time=data.get("download_time", ""),
            url=data.get("url", ""),
            file_size=data.get("file_size", 0),
            format_type=data.get("format_type", "")
        )


class RecentManager:
    """Production-ready recent downloads manager with thread safety and error handling."""

    def __init__(self, max_items: int = 20, app_name: str = "yt-dlp-gui"):
        self.max_items = max_items
        self.app_name = app_name
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{app_name}.recent")

        # Platform-specific config directory
        self.config_dir = self._get_config_directory()
        self.file_path = self.config_dir / "recent_downloads.json"

        self._ensure_directories()
        self._migrate_old_format()

    def _get_config_directory(self) -> Path:
        """Get platform-specific configuration directory."""
        import platform

        system = platform.system()
        if system == "Windows":
            base = Path(os.getenv("APPDATA", "")) / self.app_name
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support" / self.app_name
        else:  # Linux and others
            base = Path.home() / ".config" / self.app_name

        return base

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_file()
        except OSError as e:
            self.logger.error(f"Failed to create config directory: {e}")
            # Fallback to current directory
            self.file_path = Path("recent_downloads.json")
            self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the recent downloads file if it doesn't exist."""
        if not self.file_path.exists():
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
                self.logger.info(f"Created new recent downloads file: {self.file_path}")
            except (OSError, json.JSONEncodeError) as e:
                self.logger.error(f"Failed to create recent downloads file: {e}")

    def _migrate_old_format(self) -> None:
        """Migrate from old simple list format to new structured format."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if it's the old format (list of strings)
            if data and isinstance(data[0], str):
                self.logger.info("Migrating from old recent downloads format")
                migrated_items = []
                for file_path in data:
                    item = RecentItem(
                        file_path=file_path,
                        download_time=datetime.now().isoformat(),
                        url="",
                        file_size=self._get_file_size(file_path),
                        format_type="unknown"
                    )
                    migrated_items.append(item.to_dict())

                self._save_items(migrated_items)
                self.logger.info(f"Migrated {len(migrated_items)} items")

        except (OSError, json.JSONDecodeError, IndexError):
            # File doesn't exist, is empty, or already in new format
            pass

    def _get_file_size(self, file_path: str) -> int:
        """Get file size safely."""
        try:
            return Path(file_path).stat().st_size
        except OSError:
            return 0

    def _save_items(self, items: List[Dict[str, Any]]) -> None:
        """Save items to file with error handling."""
        try:
            # Create backup before saving
            backup_path = self.file_path.with_suffix(".bak")
            if self.file_path.exists():
                self.file_path.replace(backup_path)

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)

            # Remove backup on successful save
            if backup_path.exists():
                backup_path.unlink()

        except (OSError, json.JSONEncodeError) as e:
            self.logger.error(f"Failed to save recent downloads: {e}")

            # Restore backup if save failed
            backup_path = self.file_path.with_suffix(".bak")
            if backup_path.exists():
                backup_path.replace(self.file_path)

    def load(self) -> List[RecentItem]:
        """Load recent downloads with thread safety and error handling."""
        with self._lock:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                items = []
                for item_data in data:
                    try:
                        item = RecentItem.from_dict(item_data)
                        # Validate that file still exists
                        if Path(item.file_path).exists():
                            items.append(item)
                        else:
                            self.logger.debug(f"Removed missing file from recents: {item.file_path}")
                    except (TypeError, KeyError) as e:
                        self.logger.warning(f"Skipping invalid recent item: {e}")

                # If we removed missing files, save the cleaned list
                if len(items) < len(data):
                    self._save_items([item.to_dict() for item in items])

                return items

            except (OSError, json.JSONDecodeError) as e:
                self.logger.error(f"Failed to load recent downloads: {e}")
                return []

    def get_recent_items(self) -> List[RecentItem]:
        """Get recent downloads - alias for load() for backward compatibility."""
        return self.load()

    def get_recent_files(self) -> List[str]:
        """Get list of recent file paths only."""
        return [item.file_path for item in self.load()]

    def get_recent_paths(self) -> List[str]:
        """Get list of recent file paths - alias for get_recent_files()."""
        return self.get_recent_files()

    def add(self, file_path: str, url: str = "", format_type: str = "") -> None:
        """Add a new recent download with metadata."""
        with self._lock:
            try:
                # Normalize path
                file_path = str(Path(file_path).resolve())

                # Validate file exists
                if not Path(file_path).exists():
                    self.logger.warning(f"Attempted to add non-existent file: {file_path}")
                    return

                items = self.load()

                # Remove existing entry if present
                items = [item for item in items if item.file_path != file_path]

                # Create new item
                new_item = RecentItem(
                    file_path=file_path,
                    download_time=datetime.now().isoformat(),
                    url=url,
                    file_size=self._get_file_size(file_path),
                    format_type=format_type
                )

                # Add to beginning
                items.insert(0, new_item)

                # Trim to max items
                items = items[:self.max_items]

                # Save
                self._save_items([item.to_dict() for item in items])
                self.logger.info(f"Added recent download: {Path(file_path).name}")

            except Exception as e:
                self.logger.error(f"Failed to add recent download: {e}")

    def add_download(self, file_path: str, url: str = "", format_type: str = "") -> None:
        """Add a recent download - alias for add()."""
        self.add(file_path, url, format_type)

    def add_file(self, file_path: str) -> None:
        """Add a file to recent downloads - simplified version."""
        self.add(file_path)

    def remove(self, file_path: str) -> bool:
        """Remove a specific item from recent downloads."""
        with self._lock:
            try:
                file_path = str(Path(file_path).resolve())
                items = self.load()
                original_count = len(items)

                items = [item for item in items if item.file_path != file_path]

                if len(items) < original_count:
                    self._save_items([item.to_dict() for item in items])
                    self.logger.info(f"Removed from recents: {Path(file_path).name}")
                    return True

                return False

            except Exception as e:
                self.logger.error(f"Failed to remove recent download: {e}")
                return False

    def remove_item(self, file_path: str) -> bool:
        """Remove item - alias for remove()."""
        return self.remove(file_path)

    def clear(self) -> bool:
        """Clear all recent downloads."""
        with self._lock:
            try:
                self._save_items([])
                self.logger.info("Cleared all recent downloads")
                return True
            except Exception as e:
                self.logger.error(f"Failed to clear recent downloads: {e}")
                return False

    def clear_all(self) -> bool:
        """Clear all recent downloads - alias for clear()."""
        return self.clear()

    def is_recent(self, file_path: str) -> bool:
        """Check if a file is in recent downloads."""
        file_path = str(Path(file_path).resolve())
        return any(item.file_path == file_path for item in self.load())

    def get_item_by_path(self, file_path: str) -> Optional[RecentItem]:
        """Get a specific recent item by file path."""
        file_path = str(Path(file_path).resolve())
        for item in self.load():
            if item.file_path == file_path:
                return item
        return None

    def get_total_size(self) -> int:
        """Get total size of all recent downloads."""
        try:
            return sum(item.file_size for item in self.load())
        except Exception as e:
            self.logger.error(f"Failed to calculate total size: {e}")
            return 0

    def get_count(self) -> int:
        """Get total number of recent downloads."""
        return len(self.load())

    def get_max_items(self) -> int:
        """Get maximum number of items to keep."""
        return self.max_items

    def set_max_items(self, max_items: int) -> None:
        """Set maximum number of items to keep."""
        if max_items > 0:
            self.max_items = max_items
            # Trim existing items if necessary
            items = self.load()
            if len(items) > max_items:
                items = items[:max_items]
                self._save_items([item.to_dict() for item in items])

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about recent downloads."""
        try:
            items = self.load()
            if not items:
                return {
                    "total_downloads": 0,
                    "total_size_mb": 0,
                    "format_breakdown": {},
                    "oldest_download": None,
                    "newest_download": None
                }

            format_counts = {}
            for item in items:
                fmt = item.format_type or "unknown"
                format_counts[fmt] = format_counts.get(fmt, 0) + 1

            download_times = [item.download_time for item in items if item.download_time]

            return {
                "total_downloads": len(items),
                "total_size_mb": round(self.get_total_size() / (1024 * 1024), 2),
                "format_breakdown": format_counts,
                "oldest_download": min(download_times) if download_times else None,
                "newest_download": max(download_times) if download_times else None
            }

        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}

    def cleanup_missing_files(self) -> int:
        """Remove items for files that no longer exist. Returns count of removed items."""
        with self._lock:
            try:
                items = self.load()
                original_count = len(items)

                valid_items = [item for item in items if Path(item.file_path).exists()]

                if len(valid_items) < original_count:
                    self._save_items([item.to_dict() for item in valid_items])
                    removed_count = original_count - len(valid_items)
                    self.logger.info(f"Cleaned up {removed_count} missing files from recents")
                    return removed_count

                return 0

            except Exception as e:
                self.logger.error(f"Failed to cleanup missing files: {e}")
                return 0

    def export_to_file(self, export_path: str) -> bool:
        """Export recent downloads to a JSON file."""
        try:
            items = self.load()
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump([item.to_dict() for item in items], f, indent=2, ensure_ascii=False)

            self.logger.info(f"Exported {len(items)} items to {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export recent downloads: {e}")
            return False

    def import_from_file(self, import_path: str, merge: bool = True) -> bool:
        """Import recent downloads from a JSON file."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)

            imported_items = []
            for item_data in imported_data:
                try:
                    item = RecentItem.from_dict(item_data)
                    if Path(item.file_path).exists():  # Only import existing files
                        imported_items.append(item)
                except (TypeError, KeyError):
                    continue

            if merge:
                existing_items = self.load()
                # Merge, avoiding duplicates
                existing_paths = {item.file_path for item in existing_items}
                for item in imported_items:
                    if item.file_path not in existing_paths:
                        existing_items.append(item)

                # Sort by download time (newest first) and trim
                existing_items.sort(key=lambda x: x.download_time, reverse=True)
                items_to_save = existing_items[:self.max_items]
            else:
                items_to_save = imported_items[:self.max_items]

            self._save_items([item.to_dict() for item in items_to_save])
            self.logger.info(f"Imported {len(imported_items)} items from {import_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to import recent downloads: {e}")
            return False

class RecentFoldersManager:
    def __init__(self, max_items=10):
        self.max_items = max_items
        self.recent_folders = []

    def add_folder(self, folder_path: str):
        folder_path = str(Path(folder_path).resolve())
        if folder_path in self.recent_folders:
            self.recent_folders.remove(folder_path)
        self.recent_folders.insert(0, folder_path)
        self.recent_folders = self.recent_folders[:self.max_items]

    def get_recent_folders(self) -> List[str]:
        return self.recent_folders
