import os
import sys
from pathlib import Path
from typing import List
import importlib.util

from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLineEdit,
    QComboBox,
    QLabel,
    QProgressBar,
    QMenu,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QFrame,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QApplication,
)

from Core.blocker import ContentBlocker
from Core.recent import RecentFoldersManager
from Core.threads import DownloadManager, format_speed, format_duration


# class SettingsDialog(QDialog):
#     """Settings dialog for application configuration."""

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Settings")
#         self.setModal(True)
#         self.setMinimumSize(500, 400)
#         self.settings = QSettings()
#         self._init_ui()
#         self._load_settings()

#     def _init_ui(self):
#         layout = QVBoxLayout(self)

#         # Download settings
#         download_group = QGroupBox("Download Settings")
#         download_layout = QFormLayout(download_group)


#         # Default output folder
#         output_layout = QHBoxLayout()
#         self.default_output_edit = QLineEdit()
#         browse_btn = QPushButton("Browse")
#         browse_btn.clicked.connect(self._browse_default_output)
#         output_layout.addWidget(self.default_output_edit)
#         output_layout.addWidget(browse_btn)
#         download_layout.addRow("Default Output Folder:", output_layout)

#         # Automatic actions
#         self.auto_reveal_check = QCheckBox("Show in folder after download")
#         self.delete_temp_files_check = QCheckBox("Delete temporary files")
#         self.clear_url_after_download_check = QCheckBox("Clear URL after download")

#         download_layout.addRow(self.auto_reveal_check)
#         download_layout.addRow(self.delete_temp_files_check)
#         download_layout.addRow(self.clear_url_after_download_check)

#         layout.addWidget(download_group)

#         # Theme settings
#         theme_group = QGroupBox("Appearance")
#         theme_layout = QFormLayout(theme_group)

#         self.theme_combo = QComboBox()
#         self.theme_combo.addItems(["dark", "light"])
#         theme_layout.addRow("Theme:", self.theme_combo)

#         layout.addWidget(theme_group)

#         # Buttons
#         button_box = QDialogButtonBox(
#             QDialogButtonBox.StandardButton.Ok |
#             QDialogButtonBox.StandardButton.Cancel
#         )
#         button_box.accepted.connect(self._save_and_close)
#         button_box.rejected.connect(self.reject)

#         layout.addWidget(button_box)

#     def _browse_default_output(self):
#         folder = QFileDialog.getExistingDirectory(
#             self, "Select Default Output Folder",
#             self.default_output_edit.text()
#         )
#         if folder:
#             self.default_output_edit.setText(folder)

#     def _load_settings(self):
#         self.default_output_edit.setText(self.settings.value("default_output", str(Path.home() / "Downloads")))
#         self.auto_reveal_check.setChecked(self.settings.value("auto_reveal", True, bool))
#         self.delete_temp_files_check.setChecked(self.settings.value("delete_temp", True, bool))
#         self.clear_url_after_download_check.setChecked(self.settings.value("clear_url_after_download", True, bool))
#         self.theme_combo.setCurrentText(self.settings.value("theme", "dark"))

#     def _save_and_close(self):
#         # Save all settings
#         self.settings.setValue("max_concurrent", self.max_concurrent_spinbox.value())
#         self.settings.setValue("default_output", self.default_output_edit.text())
#         self.settings.setValue("auto_reveal", self.auto_reveal_check.isChecked())
#         self.settings.setValue("delete_temp", self.delete_temp_files_check.isChecked())
#         self.settings.setValue("clear_url_after_download", self.clear_url_after_download_check.isChecked())
#         self.settings.setValue("theme", self.theme_combo.currentText())

#         # Sync settings to disk
#         self.settings.sync()

#         self.accept()


class DownloadQueueWidget(QWidget):
    """Widget for managing download queue."""

    def __init__(self, download_manager: DownloadManager):
        super().__init__()
        self.download_manager = download_manager
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Download Queue"))
        header.addStretch()

        # Queue controls
        self.pause_all_btn = QPushButton("Pause All")
        self.resume_all_btn = QPushButton("Resume All")
        self.clear_completed_btn = QPushButton("Clear Completed")

        self.pause_all_btn.clicked.connect(self.download_manager.pause_all)
        self.resume_all_btn.clicked.connect(self.download_manager.resume_all)
        self.clear_completed_btn.clicked.connect(self.download_manager.clear_completed)

        header.addWidget(self.pause_all_btn)
        header.addWidget(self.resume_all_btn)
        header.addWidget(self.clear_completed_btn)

        layout.addLayout(header)

        # Downloads table
        self.downloads_table = QTableWidget()
        self.downloads_table.setColumnCount(5)
        self.downloads_table.setHorizontalHeaderLabels(
            ["File", "Status", "Progress", "Speed", "ETA"]
        )

        header = self.downloads_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.downloads_table)

        # Statistics
        self.stats_label = QLabel("Queue: 0 active, 0 queued, 0 completed")
        layout.addWidget(self.stats_label)

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_queue_display)
        self.update_timer.start(1000)

    def _connect_signals(self):
        self.download_manager.queue_status_changed.connect(self._update_stats)

    def _update_queue_display(self):
        downloads = self.download_manager.get_all_downloads_info()
        self.downloads_table.setRowCount(len(downloads))

        for row, download_info in enumerate(downloads):
            # File name
            url = download_info.get("url", "")
            filename = Path(url).name or url[:50] + "..." if len(url) > 50 else url
            self.downloads_table.setItem(row, 0, QTableWidgetItem(filename))

            # Status
            status = download_info.get("status", "unknown")
            self.downloads_table.setItem(row, 1, QTableWidgetItem(status.title()))

            # Progress
            progress_info = download_info.get("progress", {})
            progress = progress_info.get("progress", 0)
            progress_text = f"{progress:.1f}%"
            self.downloads_table.setItem(row, 2, QTableWidgetItem(progress_text))

            # Speed
            speed = progress_info.get("speed", 0)
            speed_text = format_speed(speed) if speed > 0 else "-"
            self.downloads_table.setItem(row, 3, QTableWidgetItem(speed_text))

            # ETA
            eta = progress_info.get("eta")
            eta_text = format_duration(eta) if eta else "-"
            self.downloads_table.setItem(row, 4, QTableWidgetItem(eta_text))

    def _update_stats(self, stats):
        self.stats_label.setText(
            f"Queue: {stats['active_downloads']} active, "
            f"{stats['queued_downloads']} queued, "
            f"{stats['completed_downloads']} completed"
        )


class MainWindow(QMainWindow):
    """Main window with streamlined UI and working settings."""

    def __init__(self):
        super().__init__()

        # Core components
        self.settings = QSettings("YTDLPGui", "Settings")
        self.blocker = ContentBlocker()
        self.recent_folders_manager = RecentFoldersManager()

        # Download management
        max_concurrent = self.settings.value("max_concurrent", 3, int)
        self.download_manager = DownloadManager(max_concurrent)

        # UI state
        self.current_theme = self.settings.value("theme", "dark")
        self.has_qdarktheme = self._check_qdarktheme()

        # Initialize UI
        self.setWindowTitle("YT-DLP GUI")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()
        self._apply_theme(self.current_theme)

    def _check_qdarktheme(self) -> bool:
        """Check if qdarktheme is available."""
        return importlib.util.find_spec("qdarktheme") is not None

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        central_widget.setLayout(QHBoxLayout())
        central_widget.layout().addWidget(main_splitter)

        # Left panel - Download form
        left_panel = self._create_download_panel()
        main_splitter.addWidget(left_panel)

        # Right panel - Download queue only
        self.queue_widget = DownloadQueueWidget(self.download_manager)
        main_splitter.addWidget(self.queue_widget)

        # Set splitter proportions
        main_splitter.setSizes([400, 600])

    def _create_download_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Download Options")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        # Form
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(12)

        # URL input with validation
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter video/playlist URL...")
        self.url_input.textChanged.connect(self._validate_url)
        self.url_validation_label = QLabel()
        self.url_validation_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        url_layout = QVBoxLayout()
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.url_validation_label)
        form_layout.addRow("URL:", url_layout)

        # Output path with recent folders
        output_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        default_path = self.settings.value(
            "default_output", str(Path.home() / "Downloads")
        )
        self.path_input.setText(default_path)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._browse_folder)

        self.recent_paths_btn = QPushButton("▼")
        self.recent_paths_btn.setMaximumWidth(30)
        self.recent_paths_btn.clicked.connect(self._show_recent_paths)

        output_layout.addWidget(self.path_input)
        output_layout.addWidget(self.browse_btn)
        output_layout.addWidget(self.recent_paths_btn)
        form_layout.addRow("Output:", output_layout)

        # Format selection with proper yt-dlp format strings
        self.format_combo = QComboBox()
        self.format_combo.addItems(
            [
                "Best Video + Audio",
                "Best Video Only",
                "Best Audio Only",
                "720p",
                "480p",
                "MP3 Audio",
            ]
        )
        form_layout.addRow("Format:", self.format_combo)

        # Options
        options_layout = QVBoxLayout()
        self.subtitles_check = QCheckBox("Download subtitles")
        self.metadata_check = QCheckBox("Save metadata")
        self.thumbnail_check = QCheckBox("Save thumbnail")

        options_layout.addWidget(self.subtitles_check)
        options_layout.addWidget(self.metadata_check)
        options_layout.addWidget(self.thumbnail_check)

        form_layout.addRow("Options:", options_layout)

        layout.addWidget(form_frame)

        # Download button
        self.download_btn = QPushButton("Start Download")
        self.download_btn.setObjectName("downloadButton")  # For theme styling
        self.download_btn.clicked.connect(self._start_download)
        self.download_btn.setEnabled(False)
        layout.addWidget(self.download_btn)

        # Progress section
        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)

        self.current_download_label = QLabel("No active download")
        self.current_download_label.setWordWrap(True)
        progress_layout.addWidget(self.current_download_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.progress_details_label = QLabel()
        self.progress_details_label.setStyleSheet("color: #888; font-size: 12px;")
        progress_layout.addWidget(self.progress_details_label)

        layout.addWidget(progress_frame)
        layout.addStretch()

        return panel

    def _setup_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        # file_menu = menubar.addMenu("&File")

        # settings_action = QAction("&Settings...", self)
        # settings_action.setShortcut(QKeySequence("Ctrl+,"))
        # settings_action.triggered.connect(self._open_settings)
        # file_menu.addAction(settings_action)

        # file_menu.addSeparator()

        # exit_action = QAction("E&xit", self)
        # exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        # exit_action.triggered.connect(self.close)
        # file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("ShortCuts")

        clear_url_action = QAction("Clear URL", self)
        clear_url_action.setShortcut(QKeySequence("Ctrl+D"))
        clear_url_action.triggered.connect(lambda: self.url_input.clear())
        edit_menu.addAction(clear_url_action)

        paste_url_action = QAction("Paste URL", self)
        paste_url_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_url_action.triggered.connect(self._paste_url)
        edit_menu.addAction(paste_url_action)

        # View menu for theme switching
        view_menu = menubar.addMenu("View")

        theme_menu = view_menu.addMenu("Theme")

        dark_theme_action = QAction("Dark Theme", self)
        dark_theme_action.setCheckable(True)
        dark_theme_action.triggered.connect(lambda: self._switch_theme("dark"))

        light_theme_action = QAction("Light Theme", self)
        light_theme_action.setCheckable(True)
        light_theme_action.triggered.connect(lambda: self._switch_theme("light"))

        theme_menu.addAction(dark_theme_action)
        theme_menu.addAction(light_theme_action)

        # Set initial theme action state
        if self.current_theme == "dark":
            dark_theme_action.setChecked(True)
        else:
            light_theme_action.setChecked(True)

        self.dark_theme_action = dark_theme_action
        self.light_theme_action = light_theme_action

    def _setup_status_bar(self):
        self.status_bar = self.statusBar()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Download stats
        self.stats_status_label = QLabel("Downloads: 0 active")
        self.status_bar.addPermanentWidget(self.stats_status_label)

        # Theme status
        self.theme_status_label = QLabel(f"Theme: {self.current_theme}")
        self.status_bar.addPermanentWidget(self.theme_status_label)

    def _connect_signals(self):
        # Download manager signals
        self.download_manager.download_started.connect(self._on_download_started)
        self.download_manager.download_finished.connect(self._on_download_finished)
        self.download_manager.download_error.connect(self._on_download_error)
        self.download_manager.download_progress.connect(self._on_download_progress)

        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)
        self.update_timer.start(5000)

    def _validate_url(self, url: str):
        if not url.strip():
            self.url_validation_label.setText("")
            self.download_btn.setEnabled(False)
            return

        url = url.strip()

        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            self.url_validation_label.setText("URL must start with http:// or https://")
            self.url_validation_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.download_btn.setEnabled(False)
            return

        # Check if URL is blocked (if blocker is available)
        try:
            block_result = self.blocker.is_blocked(url)
            if block_result.is_blocked:
                self.url_validation_label.setText(
                    f"URL blocked: {block_result.details}"
                )
                self.url_validation_label.setStyleSheet(
                    "color: #ff6b6b; font-size: 12px;"
                )
                self.download_btn.setEnabled(False)
                return
        except Exception:
            # If blocker fails, continue without blocking
            pass

        self.url_validation_label.setText("✓")
        self.url_validation_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.download_btn.setEnabled(True)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.path_input.text()
        )
        if folder:
            self.path_input.setText(folder)
            self.recent_folders_manager.add_folder(folder)

    def _show_recent_paths(self):
        menu = QMenu(self)
        recent_folders = self.recent_folders_manager.get_recent_folders()

        if not recent_folders:
            menu.addAction("No recent folders").setEnabled(False)
        else:
            for folder in recent_folders:
                action = menu.addAction(str(Path(folder).name))
                action.triggered.connect(
                    lambda checked, f=folder: self.path_input.setText(f)
                )

        menu.exec(
            self.recent_paths_btn.mapToGlobal(self.recent_paths_btn.rect().bottomLeft())
        )

    def _start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a URL to download.")
            return

        output_path = self.path_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Warning", "Please specify an output folder.")
            return

        # Create download options with proper yt-dlp format strings
        format_string = self._get_format_string()

        config_options = {
            "format": format_string,
            "writesubtitles": self.subtitles_check.isChecked(),
            "writeinfojson": self.metadata_check.isChecked(),
            "writethumbnail": self.thumbnail_check.isChecked(),
        }

        # Add to download queue
        try:
            _ = self.download_manager.add_download(url, output_path, config_options)

            # Add to recent folders
            self.recent_folders_manager.add_folder(output_path)

            # Update UI
            self.current_download_label.setText(
                f"Downloading: {url[:60]}..." if len(url) > 60 else url
            )
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # Clear URL input if setting is enabled
            if self.settings.value("clear_url_after_download", True, bool):
                self.url_input.clear()

            self.status_label.setText("Download started")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start download: {str(e)}")

    def _get_format_string(self) -> str:
        """Convert format selection to proper yt-dlp format string."""
        format_text = self.format_combo.currentText()

        # Proper yt-dlp format strings that prioritize quality over format
        format_map = {
            "Best Video + Audio": "bv*+ba/b",  # Best video + best audio, any format
            "Best Video Only": "bv*",  # Best video only, any format
            "Best Audio Only": "ba*",  # Best audio only, any format
            "720p": "bv*[height<=720]+ba/b[height<=720]",  # Max 720p, any format
            "480p": "bv*[height<=480]+ba/b[height<=480]",  # Max 480p, any format
            "MP3 Audio": "ba*",  # Best audio (you'd handle MP3 conversion separately)
        }

        return format_map.get(format_text, "bv*+ba/b")

    def _on_download_started(self, url: str):
        self.status_label.setText(f"Download started: {Path(url).name}")

    def _on_download_finished(self, success: bool, message: str, file_paths: List[str]):
        self.status_label.setText(
            f"Download {'completed' if success else 'failed'}: {message}"
        )

        if success and file_paths:
            # Auto-reveal file if enabled
            if self.settings.value("auto_reveal", True, bool) and file_paths:
                self._reveal_in_folder(file_paths[0])
        else:
            QMessageBox.critical(self, "Download Error", f"Download failed: {message}")

    def _on_download_error(self, error_type: str, error_message: str):
        self.status_label.setText(f"Download error: {error_message}")
        QMessageBox.critical(
            self, "Download Error", f"Download failed:\n{error_message}"
        )

    def _on_download_progress(self, download_id: str, progress_info: dict):
        progress = progress_info.get("progress", 0)
        speed = progress_info.get("speed", 0)
        eta = progress_info.get("eta")

        self.progress_bar.setValue(int(progress))

        details = f"Speed: {format_speed(speed)} | ETA: {format_duration(eta) if eta else 'Unknown'}"
        self.progress_details_label.setText(details)

    def _periodic_update(self):
        # Update download statistics in status bar
        try:
            count = self.download_manager.get_download_count()
            self.stats_status_label.setText(f"Downloads: {count['active']} active")

            # Hide progress if no active downloads
            if count["active"] == 0:
                self.progress_bar.setVisible(False)
                self.current_download_label.setText("No active download")
                self.progress_details_label.setText("")
        except Exception:
            pass

    def _switch_theme(self, theme: str):
        """Switch to the specified theme and update settings."""
        if theme != self.current_theme:
            self.current_theme = theme
            self.settings.setValue("theme", theme)
            self.settings.sync()

            # Update menu checkboxes
            if hasattr(self, "dark_theme_action") and hasattr(
                self, "light_theme_action"
            ):
                self.dark_theme_action.setChecked(theme == "dark")
                self.light_theme_action.setChecked(theme == "light")

            self._apply_theme(theme)

    def _apply_theme(self, theme: str):
        """Apply the specified theme with improved styling."""
        self.current_theme = theme

        if self.has_qdarktheme:
            try:
                import qdarktheme

                # Clear any existing stylesheet first
                self.setStyleSheet("")
                qdarktheme.setup_theme(theme)

                # Add custom button styling for the download button
                download_btn_style = """
                QPushButton#downloadButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton#downloadButton:hover {
                    background-color: #45a049;
                }
                QPushButton#downloadButton:disabled {
                    background-color: #666;
                    color: #ccc;
                }
                """
                self.setStyleSheet(download_btn_style)

                status_message = f"Applied {theme} theme (qdarktheme)"
            except Exception as e:
                print(f"qdarktheme failed: {e}")
                self.has_qdarktheme = False
                self._apply_fallback_theme(theme)
                status_message = f"Applied {theme} theme (fallback - qdarktheme failed)"
        else:
            self._apply_fallback_theme(theme)
            status_message = f"Applied {theme} theme (fallback styling)"

        # Update status bar
        if hasattr(self, "theme_status_label"):
            self.theme_status_label.setText(f"Theme: {theme}")

        if hasattr(self, "status_label"):
            self.status_label.setText(status_message)

    def _apply_fallback_theme(self, theme: str):
        """Apply fallback theme styling when qdarktheme is not available."""
        if theme == "dark":
            dark_stylesheet = """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 2px solid #555;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
            QPushButton {
                background-color: #404040;
                border: 2px solid #555;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QPushButton#downloadButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton#downloadButton:hover {
                background-color: #45a049;
            }
            QPushButton#downloadButton:disabled {
                background-color: #666;
                color: #ccc;
            }
            QComboBox {
                background-color: #3c3c3c;
                border: 2px solid #555;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #777;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #404040;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555;
                border-radius: 3px;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #45a049;
            }
            QLabel {
                color: #ffffff;
            }
            QGroupBox {
                color: #ffffff;
                border: 2px solid #555;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                background-color: #2b2b2b;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                background-color: #3c3c3c;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QTableWidget {
                background-color: #3c3c3c;
                alternate-background-color: #404040;
                border: 1px solid #555;
                gridline-color: #555;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #404040;
                padding: 8px;
                border: 1px solid #555;
                font-weight: bold;
            }
            QMenuBar {
                background-color: #404040;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background-color: #4CAF50;
            }
            QMenu {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
            QStatusBar {
                background-color: #404040;
                color: #ffffff;
                border-top: 1px solid #555;
            }
            QSplitter::handle {
                background-color: #555;
                width: 2px;
                height: 2px;
            }
            QFrame {
                border: 1px solid #555;
                border-radius: 5px;
            }
            """
            self.setStyleSheet(dark_stylesheet)
        else:
            # Light theme
            light_stylesheet = """
            QMainWindow {
                background-color: #ffffff;
                color: #333333;
            }
            QWidget {
                background-color: #ffffff;
                color: #333333;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #ddd;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
            QPushButton {
                background-color: #f5f5f5;
                border: 2px solid #ddd;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
                border-color: #ccc;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QPushButton#downloadButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton#downloadButton:hover {
                background-color: #45a049;
            }
            QPushButton#downloadButton:disabled {
                background-color: #ccc;
                color: #888;
            }
            QComboBox {
                background-color: #ffffff;
                border: 2px solid #ddd;
                padding: 8px;
                border-radius: 4px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #ccc;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #f5f5f5;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #333333;
            }
            QCheckBox {
                color: #333333;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #ddd;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #45a049;
            }
            QLabel {
                color: #333333;
            }
            QGroupBox {
                color: #333333;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                background-color: #ffffff;
            }
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                background-color: #f5f5f5;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f9f9f9;
                border: 1px solid #ddd;
                gridline-color: #ddd;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
            QMenuBar {
                background-color: #f5f5f5;
                color: #333333;
            }
            QMenuBar::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QMenu {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #ddd;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QStatusBar {
                background-color: #f5f5f5;
                color: #333333;
                border-top: 1px solid #ddd;
            }
            QSplitter::handle {
                background-color: #ddd;
                width: 2px;
                height: 2px;
            }
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            """
            self.setStyleSheet(light_stylesheet)

    def _paste_url(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and (text.startswith("http://") or text.startswith("https://")):
            self.url_input.setText(text)

    # def _open_settings(self):
    #     dialog = SettingsDialog(self)
    #     if dialog.exec() == QDialog.DialogCode.Accepted:
    #         # Apply new settings immediately
    #         new_theme = self.settings.value("theme", "dark")
    #         if new_theme != self.current_theme:
    #             self._switch_theme(new_theme)

    #         # Update default output path
    #         default_output = self.settings.value("default_output", str(Path.home() / "Downloads"))
    #         if not self.path_input.text() or self.path_input.text() == str(Path.home() / "Downloads"):
    #             self.path_input.setText(default_output)

    #         # Update download manager settings
    #         try:
    #             max_concurrent = self.settings.value("max_concurrent", 3, int)
    #             self.download_manager.set_max_concurrent_downloads(max_concurrent)
    #         except:
    #             pass

    #         self.status_label.setText("Settings applied")

    def _reveal_in_folder(self, filepath: str):
        path = Path(filepath)
        if path.exists():
            if sys.platform == "win32":
                os.startfile(path.parent)
            elif sys.platform == "darwin":
                os.system(f'open -R "{path}"')
            else:
                os.system(f'xdg-open "{path.parent}"')

    def closeEvent(self, event: QCloseEvent):
        # Check if downloads are active
        try:
            count = self.download_manager.get_download_count()
            if count["active"] > 0:
                reply = QMessageBox.question(
                    self,
                    "Active Downloads",
                    f"There are {count['active']} active downloads.\n"
                    "Do you want to close anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
                else:
                    # Cancel all active downloads
                    self.download_manager.cancel_all()
        except Exception:
            pass

        # Stop timers
        if hasattr(self, "update_timer"):
            self.update_timer.stop()

        if hasattr(self, "queue_widget") and hasattr(self.queue_widget, "update_timer"):
            self.queue_widget.update_timer.stop()

        # Stop download manager
        try:
            self.download_manager.stop_manager()
        except Exception:
            pass

        event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("YT-DLP GUI")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("YTDLPGui")
    app.setOrganizationDomain("ytdlp-gui.local")

    # Create and show main window
    try:
        window = MainWindow()
        window.show()

        # Run the application
        sys.exit(app.exec())

    except Exception as e:
        # Show error dialog if main window fails to initialize
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("Startup Error")
        error_dialog.setText("Failed to initialize application")
        error_dialog.setDetailedText(str(e))
        error_dialog.exec()

        sys.exit(1)


if __name__ == "__main__":
    main()
