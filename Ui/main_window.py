import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import webbrowser

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QSettings, pyqtSignal, QThread, QSize
)
from PyQt6.QtGui import (
    QAction, QFont, QDesktopServices, QIcon, QPixmap, QKeySequence,
    QShortcut, QCloseEvent
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QComboBox, QLabel, QProgressBar, QMenu,
    QCheckBox, QFileDialog, QMessageBox, QFrame, QStyle, QSizePolicy,
    QListWidget, QListWidgetItem, QTabWidget, QTextEdit, QSpinBox,
    QGroupBox, QSlider, QStatusBar, QMenuBar, QToolBar, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QGridLayout, QApplication, QScrollArea
)

from Core.blocker import ContentBlocker, BlockResult
from Core.recent import RecentManager, RecentItem, RecentFoldersManager
from Core.threads import (
    DownloadThread, DownloadManager, DownloadProgress, DownloadStatus,
    format_bytes, format_speed, format_duration
)


class CustomRulesDialog(QDialog):
    """Dialog for managing custom blocking rules."""

    def __init__(self, blocker: ContentBlocker, parent=None):
        super().__init__(parent)
        self.blocker = blocker
        self.setWindowTitle("Manage Custom Blocking Rules")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self._init_ui()
        self._load_rules()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Tabs for different rule types
        tab_widget = QTabWidget()

        # Domain rules tab
        domain_tab = self._create_domain_tab()
        tab_widget.addTab(domain_tab, "Domains")

        # Keyword rules tab
        keyword_tab = self._create_keyword_tab()
        tab_widget.addTab(keyword_tab, "Keywords")

        # Pattern rules tab
        pattern_tab = self._create_pattern_tab()
        tab_widget.addTab(pattern_tab, "Patterns")

        # Whitelist tab
        whitelist_tab = self._create_whitelist_tab()
        tab_widget.addTab(whitelist_tab, "Whitelist")

        layout.addWidget(tab_widget)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_domain_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Add domain section
        add_layout = QHBoxLayout()
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("Enter domain (e.g., example.com)")
        add_domain_btn = QPushButton("Add Domain")
        add_domain_btn.clicked.connect(self._add_domain_rule)

        add_layout.addWidget(QLabel("Domain:"))
        add_layout.addWidget(self.domain_input)
        add_layout.addWidget(add_domain_btn)
        layout.addLayout(add_layout)

        # Domain list
        self.domain_list = QListWidget()
        self.domain_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.domain_list.customContextMenuRequested.connect(self._show_domain_context_menu)
        layout.addWidget(self.domain_list)

        return widget

    def _create_keyword_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Add keyword section
        add_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Enter keyword")
        self.case_sensitive_check = QCheckBox("Case Sensitive")
        add_keyword_btn = QPushButton("Add Keyword")
        add_keyword_btn.clicked.connect(self._add_keyword_rule)

        add_layout.addWidget(QLabel("Keyword:"))
        add_layout.addWidget(self.keyword_input)
        add_layout.addWidget(self.case_sensitive_check)
        add_layout.addWidget(add_keyword_btn)
        layout.addLayout(add_layout)

        # Keyword list
        self.keyword_list = QListWidget()
        self.keyword_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.keyword_list.customContextMenuRequested.connect(self._show_keyword_context_menu)
        layout.addWidget(self.keyword_list)

        return widget

    def _create_pattern_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Add pattern section
        add_layout = QHBoxLayout()
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Enter regex pattern")
        add_pattern_btn = QPushButton("Add Pattern")
        add_pattern_btn.clicked.connect(self._add_pattern_rule)

        add_layout.addWidget(QLabel("Pattern:"))
        add_layout.addWidget(self.pattern_input)
        add_layout.addWidget(add_pattern_btn)
        layout.addLayout(add_layout)

        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pattern_list.customContextMenuRequested.connect(self._show_pattern_context_menu)
        layout.addWidget(self.pattern_list)

        return widget

    def _create_whitelist_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Add whitelist section
        add_layout = QHBoxLayout()
        self.whitelist_input = QLineEdit()
        self.whitelist_input.setPlaceholderText("Enter domain to whitelist")
        add_whitelist_btn = QPushButton("Add to Whitelist")
        add_whitelist_btn.clicked.connect(self._add_whitelist_domain)

        add_layout.addWidget(QLabel("Domain:"))
        add_layout.addWidget(self.whitelist_input)
        add_layout.addWidget(add_whitelist_btn)
        layout.addLayout(add_layout)

        # Whitelist list
        self.whitelist_list = QListWidget()
        self.whitelist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.whitelist_list.customContextMenuRequested.connect(self._show_whitelist_context_menu)
        layout.addWidget(self.whitelist_list)

        return widget

    def _load_rules(self):
        """Load all rules from the blocker."""
        rules = self.blocker.get_all_rules()

        # Load domain rules
        self.domain_list.clear()
        for rule_data in rules.get("domains", []):
            item = QListWidgetItem(f"{rule_data['value']} ({'enabled' if rule_data['enabled'] else 'disabled'})")
            item.setData(Qt.ItemDataRole.UserRole, rule_data)
            self.domain_list.addItem(item)

        # Load keyword rules
        self.keyword_list.clear()
        for rule_data in rules.get("keywords", []):
            case_text = " (case-sensitive)" if rule_data.get('case_sensitive') else ""
            item = QListWidgetItem(f"{rule_data['value']}{case_text} ({'enabled' if rule_data['enabled'] else 'disabled'})")
            item.setData(Qt.ItemDataRole.UserRole, rule_data)
            self.keyword_list.addItem(item)

        # Load pattern rules
        self.pattern_list.clear()
        for rule_data in rules.get("patterns", []):
            item = QListWidgetItem(f"{rule_data['value']} ({'enabled' if rule_data['enabled'] else 'disabled'})")
            item.setData(Qt.ItemDataRole.UserRole, rule_data)
            self.pattern_list.addItem(item)

        # Load whitelist
        self.whitelist_list.clear()
        for domain in rules.get("whitelist", []):
            item = QListWidgetItem(domain)
            self.whitelist_list.addItem(item)

    def _add_domain_rule(self):
        domain = self.domain_input.text().strip()
        if domain:
            if self.blocker.add_domain_rule(domain, f"User-added domain: {domain}"):
                self.domain_input.clear()
                self._load_rules()
            else:
                QMessageBox.warning(self, "Error", "Failed to add domain rule or rule already exists.")

    def _add_keyword_rule(self):
        keyword = self.keyword_input.text().strip()
        if keyword:
            case_sensitive = self.case_sensitive_check.isChecked()
            if self.blocker.add_keyword_rule(keyword, case_sensitive, f"User-added keyword: {keyword}"):
                self.keyword_input.clear()
                self.case_sensitive_check.setChecked(False)
                self._load_rules()
            else:
                QMessageBox.warning(self, "Error", "Failed to add keyword rule or rule already exists.")

    def _add_pattern_rule(self):
        pattern = self.pattern_input.text().strip()
        if pattern:
            if self.blocker.add_pattern_rule(pattern, f"User-added pattern: {pattern}"):
                self.pattern_input.clear()
                self._load_rules()
            else:
                QMessageBox.warning(self, "Error", "Failed to add pattern rule. Check regex syntax.")

    def _add_whitelist_domain(self):
        domain = self.whitelist_input.text().strip()
        if domain:
            self.blocker.add_to_whitelist(domain)
            self.whitelist_input.clear()
            self._load_rules()

    def _show_domain_context_menu(self, position):
        if self.domain_list.itemAt(position):
            menu = QMenu(self)
            toggle_action = menu.addAction("Toggle Enable/Disable")
            remove_action = menu.addAction("Remove Rule")

            action = menu.exec(self.domain_list.mapToGlobal(position))
            if action == toggle_action:
                self._toggle_domain_rule()
            elif action == remove_action:
                self._remove_domain_rule()

    def _toggle_domain_rule(self):
        item = self.domain_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.toggle_rule("domain", rule_data['value'])
            self._load_rules()

    def _remove_domain_rule(self):
        item = self.domain_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.remove_rule("domain", rule_data['value'])
            self._load_rules()

    def _show_keyword_context_menu(self, position):
        if self.keyword_list.itemAt(position):
            menu = QMenu(self)
            toggle_action = menu.addAction("Toggle Enable/Disable")
            remove_action = menu.addAction("Remove Rule")

            action = menu.exec(self.keyword_list.mapToGlobal(position))
            if action == toggle_action:
                self._toggle_keyword_rule()
            elif action == remove_action:
                self._remove_keyword_rule()

    def _toggle_keyword_rule(self):
        item = self.keyword_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.toggle_rule("keyword", rule_data['value'])
            self._load_rules()

    def _remove_keyword_rule(self):
        item = self.keyword_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.remove_rule("keyword", rule_data['value'])
            self._load_rules()

    def _show_pattern_context_menu(self, position):
        if self.pattern_list.itemAt(position):
            menu = QMenu(self)
            toggle_action = menu.addAction("Toggle Enable/Disable")
            remove_action = menu.addAction("Remove Rule")

            action = menu.exec(self.pattern_list.mapToGlobal(position))
            if action == toggle_action:
                self._toggle_pattern_rule()
            elif action == remove_action:
                self._remove_pattern_rule()

    def _toggle_pattern_rule(self):
        item = self.pattern_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.toggle_rule("pattern", rule_data['value'])
            self._load_rules()

    def _remove_pattern_rule(self):
        item = self.pattern_list.currentItem()
        if item:
            rule_data = item.data(Qt.ItemDataRole.UserRole)
            self.blocker.remove_rule("pattern", rule_data['value'])
            self._load_rules()

    def _show_whitelist_context_menu(self, position):
        if self.whitelist_list.itemAt(position):
            menu = QMenu(self)
            remove_action = menu.addAction("Remove from Whitelist")

            action = menu.exec(self.whitelist_list.mapToGlobal(position))
            if action == remove_action:
                self._remove_whitelist_domain()

    def _remove_whitelist_domain(self):
        item = self.whitelist_list.currentItem()
        if item:
            domain = item.text()
            self.blocker.remove_from_whitelist(domain)
            self._load_rules()


# class SettingsDialog(QDialog):
#     """Settings dialog for application configuration."""

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Settings")
#         self.setModal(True)
#         self.setMinimumSize(600, 500)
#         self.settings = QSettings()
#         self._init_ui()
#         self._load_settings()

#     def _init_ui(self):
#         layout = QVBoxLayout(self)

#         # Create tabs
#         tab_widget = QTabWidget()

#         # General tab
#         general_tab = self._create_general_tab()
#         tab_widget.addTab(general_tab, "General")

#         # Download tab
#         download_tab = self._create_download_tab()
#         tab_widget.addTab(download_tab, "Downloads")

#         # Blocking tab
#         blocking_tab = self._create_blocking_tab()
#         tab_widget.addTab(blocking_tab, "Content Filter")

#         # Advanced tab
#         advanced_tab = self._create_advanced_tab()
#         tab_widget.addTab(advanced_tab, "Advanced")

#         layout.addWidget(tab_widget)

#         # Buttons
#         button_box = QDialogButtonBox(
#             QDialogButtonBox.StandardButton.Ok |
#             QDialogButtonBox.StandardButton.Cancel |
#             QDialogButtonBox.StandardButton.Apply
#         )
#         button_box.accepted.connect(self._save_and_close)
#         button_box.rejected.connect(self.reject)
#         button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._save_settings)

#         layout.addWidget(button_box)

#     def _create_general_tab(self) -> QWidget:
#         widget = QWidget()
#         layout = QVBoxLayout(widget)

#         # Theme settings
#         theme_group = QGroupBox("Appearance")
#         theme_layout = QFormLayout(theme_group)

#         self.theme_combo = QComboBox()
#         self.theme_combo.addItems(["dark", "light", "auto"])
#         theme_layout.addRow("Theme:", self.theme_combo)

#         self.window_size_combo = QComboBox()
#         self.window_size_combo.addItems(["960x640", "1200x800", "1440x900"])
#         theme_layout.addRow("Window Size:", self.window_size_combo)

#         layout.addWidget(theme_group)

#         # Startup settings
#         startup_group = QGroupBox("Startup")
#         startup_layout = QFormLayout(startup_group)

#         self.restore_session_check = QCheckBox("Restore previous session")
#         self.minimize_to_tray_check = QCheckBox("Minimize to system tray")

#         startup_layout.addRow(self.restore_session_check)
#         startup_layout.addRow(self.minimize_to_tray_check)

#         layout.addWidget(startup_group)

#         layout.addStretch()
#         return widget

#     def _create_download_tab(self) -> QWidget:
#         widget = QWidget()
#         layout = QVBoxLayout(widget)

#         # Download settings
#         download_group = QGroupBox("Download Behavior")
#         download_layout = QFormLayout(download_group)

#         self.max_concurrent_spinbox = QSpinBox()
#         self.max_concurrent_spinbox.setRange(1, 10)
#         self.max_concurrent_spinbox.setValue(3)
#         download_layout.addRow("Max Concurrent Downloads:", self.max_concurrent_spinbox)

#         self.default_format_combo = QComboBox()
#         self.default_format_combo.addItems([
#             "Best Quality (Video + Audio)",
#             "Best Video Only",
#             "Best Audio Only",
#             "720p Video + Audio",
#             "480p Video + Audio",
#             "MP3 Audio Only"
#         ])
#         download_layout.addRow("Default Format:", self.default_format_combo)

#         self.default_output_edit = QLineEdit()
#         browse_btn = QPushButton("Browse")
#         browse_btn.clicked.connect(self._browse_default_output)
#         output_layout = QHBoxLayout()
#         output_layout.addWidget(self.default_output_edit)
#         output_layout.addWidget(browse_btn)
#         download_layout.addRow("Default Output Folder:", output_layout)

#         layout.addWidget(download_group)

#         # Automatic actions
#         auto_group = QGroupBox("Automatic Actions")
#         auto_layout = QFormLayout(auto_group)

#         self.auto_open_check = QCheckBox("Open file after download")
#         self.auto_reveal_check = QCheckBox("Show in folder after download")
#         self.delete_temp_files_check = QCheckBox("Delete temporary files")
#         self.clear_url_after_download_check = QCheckBox("Clear URL after download")

#         auto_layout.addRow(self.auto_open_check)
#         auto_layout.addRow(self.auto_reveal_check)
#         auto_layout.addRow(self.delete_temp_files_check)
#         auto_layout.addRow(self.clear_url_after_download_check)

#         layout.addWidget(auto_group)

#         layout.addStretch()
#         return widget

#     def _create_blocking_tab(self) -> QWidget:
#         widget = QWidget()
#         layout = QVBoxLayout(widget)

#         # Enable blocking
#         self.enable_blocking_check = QCheckBox("Enable content filtering")
#         layout.addWidget(self.enable_blocking_check)

#         # Blocking level
#         level_group = QGroupBox("Filtering Level")
#         level_layout = QVBoxLayout(level_group)

#         self.blocking_level_slider = QSlider(Qt.Orientation.Horizontal)
#         self.blocking_level_slider.setRange(1, 3)
#         self.blocking_level_slider.setValue(2)
#         self.blocking_level_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
#         self.blocking_level_slider.valueChanged.connect(self._update_blocking_level_label)

#         self.blocking_level_label = QLabel("Medium")
#         self.blocking_level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

#         level_layout.addWidget(QLabel("Low          Medium          High"))
#         level_layout.addWidget(self.blocking_level_slider)
#         level_layout.addWidget(self.blocking_level_label)

#         layout.addWidget(level_group)

#         # Custom rules button
#         custom_rules_btn = QPushButton("Manage Custom Rules...")
#         custom_rules_btn.clicked.connect(self._open_custom_rules_dialog)
#         layout.addWidget(custom_rules_btn)

#         layout.addStretch()
#         return widget

#     def _create_advanced_tab(self) -> QWidget:
#         widget = QWidget()
#         layout = QVBoxLayout(widget)

#         # Network settings
#         network_group = QGroupBox("Network")
#         network_layout = QFormLayout(network_group)

#         self.timeout_spinbox = QSpinBox()
#         self.timeout_spinbox.setRange(10, 300)
#         self.timeout_spinbox.setValue(60)
#         self.timeout_spinbox.setSuffix(" seconds")
#         network_layout.addRow("Connection Timeout:", self.timeout_spinbox)

#         self.retries_spinbox = QSpinBox()
#         self.retries_spinbox.setRange(0, 10)
#         self.retries_spinbox.setValue(3)
#         network_layout.addRow("Download Retries:", self.retries_spinbox)

#         layout.addWidget(network_group)

#         # Performance settings
#         perf_group = QGroupBox("Performance")
#         perf_layout = QFormLayout(perf_group)

#         self.cache_size_spinbox = QSpinBox()
#         self.cache_size_spinbox.setRange(50, 10000)
#         self.cache_size_spinbox.setValue(1000)
#         perf_layout.addRow("Cache Size:", self.cache_size_spinbox)

#         layout.addWidget(perf_group)

#         layout.addStretch()
#         return widget

#     def _browse_default_output(self):
#         folder = QFileDialog.getExistingDirectory(
#             self, "Select Default Output Folder",
#             self.default_output_edit.text()
#         )
#         if folder:
#             self.default_output_edit.setText(folder)

#     def _update_blocking_level_label(self, value):
#         levels = {1: "Low", 2: "Medium", 3: "High"}
#         self.blocking_level_label.setText(levels.get(value, "Medium"))

#     def _open_custom_rules_dialog(self):
#         if hasattr(self.parent(), 'blocker'):
#             dialog = CustomRulesDialog(self.parent().blocker, self)
#             dialog.exec()
#         else:
#             QMessageBox.information(self, "Custom Rules",
#                                   "Custom rules management is not available.")

#     def _load_settings(self):
#         self.theme_combo.setCurrentText(self.settings.value("theme", "dark"))
#         self.window_size_combo.setCurrentText(self.settings.value("window_size", "960x640"))
#         self.restore_session_check.setChecked(self.settings.value("restore_session", True, bool))
#         self.minimize_to_tray_check.setChecked(self.settings.value("minimize_to_tray", False, bool))

#         self.max_concurrent_spinbox.setValue(self.settings.value("max_concurrent", 3, int))
#         self.default_format_combo.setCurrentText(self.settings.value("default_format", "Best Quality (Video + Audio)"))
#         self.default_output_edit.setText(self.settings.value("default_output", str(Path.home() / "Downloads")))

#         self.auto_open_check.setChecked(self.settings.value("auto_open", False, bool))
#         self.auto_reveal_check.setChecked(self.settings.value("auto_reveal", True, bool))
#         self.delete_temp_files_check.setChecked(self.settings.value("delete_temp", True, bool))
#         self.clear_url_after_download_check.setChecked(self.settings.value("clear_url_after_download", True, bool))

#         self.enable_blocking_check.setChecked(self.settings.value("enable_blocking", True, bool))
#         self.blocking_level_slider.setValue(self.settings.value("blocking_level", 2, int))

#         self.timeout_spinbox.setValue(self.settings.value("timeout", 60, int))
#         self.retries_spinbox.setValue(self.settings.value("retries", 3, int))
#         self.cache_size_spinbox.setValue(self.settings.value("cache_size", 1000, int))

#     def _save_settings(self):
#         self.settings.setValue("theme", self.theme_combo.currentText())
#         self.settings.setValue("window_size", self.window_size_combo.currentText())
#         self.settings.setValue("restore_session", self.restore_session_check.isChecked())
#         self.settings.setValue("minimize_to_tray", self.minimize_to_tray_check.isChecked())

#         self.settings.setValue("max_concurrent", self.max_concurrent_spinbox.value())
#         self.settings.setValue("default_format", self.default_format_combo.currentText())
#         self.settings.setValue("default_output", self.default_output_edit.text())

#         self.settings.setValue("auto_open", self.auto_open_check.isChecked())
#         self.settings.setValue("auto_reveal", self.auto_reveal_check.isChecked())
#         self.settings.setValue("delete_temp", self.delete_temp_files_check.isChecked())
#         self.settings.setValue("clear_url_after_download", self.clear_url_after_download_check.isChecked())

#         self.settings.setValue("enable_blocking", self.enable_blocking_check.isChecked())
#         self.settings.setValue("blocking_level", self.blocking_level_slider.value())

#         self.settings.setValue("timeout", self.timeout_spinbox.value())
#         self.settings.setValue("retries", self.retries_spinbox.value())
#         self.settings.setValue("cache_size", self.cache_size_spinbox.value())

#     def _save_and_close(self):
#         self._save_settings()
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
        self.downloads_table.setColumnCount(6)
        self.downloads_table.setHorizontalHeaderLabels([
            "File", "Status", "Progress", "Speed", "ETA", "Actions"
        ])

        header = self.downloads_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # Context menu
        self.downloads_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.downloads_table.customContextMenuRequested.connect(self._show_context_menu)

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
            # Store download ID for context menu
            download_id = download_info.get("download_id", "")

            # File name
            url = download_info.get("url", "")
            filename = Path(url).name or url[:50] + "..." if len(url) > 50 else url
            filename_item = QTableWidgetItem(filename)
            filename_item.setData(Qt.ItemDataRole.UserRole, download_id)
            self.downloads_table.setItem(row, 0, filename_item)

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

            # Actions (simplified display)
            actions_text = "⏸️ ❌" if status == "downloading" else "▶️ ❌"
            self.downloads_table.setItem(row, 5, QTableWidgetItem(actions_text))

    def _update_stats(self, stats):
        self.stats_label.setText(
            f"Queue: {stats['active_downloads']} active, "
            f"{stats['queued_downloads']} queued, "
            f"{stats['completed_downloads']} completed"
        )

    def _show_context_menu(self, position):
        """Show context menu for download items."""
        item = self.downloads_table.itemAt(position)
        if not item:
            return

        download_id = item.data(Qt.ItemDataRole.UserRole)
        if not download_id:
            return

        menu = QMenu(self)

        # Get download info to determine available actions
        download_thread = self.download_manager.get_download_by_id(download_id)
        if download_thread:
            status = download_thread._current_progress.status

            if status == DownloadStatus.DOWNLOADING:
                pause_action = menu.addAction("Pause")
                pause_action.triggered.connect(lambda: self.download_manager.pause_download(download_id))
            elif status == DownloadStatus.PAUSED:
                resume_action = menu.addAction("Resume")
                resume_action.triggered.connect(lambda: self.download_manager.resume_download(download_id))

            menu.addSeparator()
            cancel_action = menu.addAction("Cancel")
            cancel_action.triggered.connect(lambda: self.download_manager.remove_download(download_id))

        menu.exec(self.downloads_table.mapToGlobal(position))


class MainWindow(QMainWindow):
    """Enhanced main window with integrated content blocking and download management."""

    def __init__(self):
        super().__init__()

        # Core components
        self.settings = QSettings("YTDLPGui", "Settings")
        self.blocker = ContentBlocker()
        self.recent_manager = RecentManager(app_name="yt-dlp-gui")
        self.recent_folders_manager = RecentFoldersManager()

        # Download management
        max_concurrent = self.settings.value("max_concurrent", 3, int)
        self.download_manager = DownloadManager(max_concurrent)

        # UI state
        self.current_theme = self.settings.value("theme", "dark")

        # Initialize UI
        self.setWindowTitle("YT-DLP GUI - Enhanced")
        self.setMinimumSize(1200, 800)
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._connect_signals()
        self._load_session()

        # Apply theme (if qdarktheme is available)
        try:
            import qdarktheme
            qdarktheme.setup_theme(self.current_theme)
        except ImportError:
            # Fallback styling if qdarktheme is not available
            if self.current_theme == "dark":
                self.setStyleSheet("""
                    QMainWindow { background-color: #2b2b2b; color: #ffffff; }
                    QWidget { background-color: #2b2b2b; color: #ffffff; }
                    QLineEdit { background-color: #3c3c3c; border: 1px solid #555; padding: 5px; }
                    QPushButton { background-color: #404040; border: 1px solid #555; padding: 5px; }
                    QPushButton:hover { background-color: #4a4a4a; }
                """)

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

        # Right panel - Tabs
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter proportions
        main_splitter.setSizes([400, 800])

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
        default_path = self.settings.value("default_output", str(Path.home() / "Downloads"))
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

        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Best Quality (Video + Audio)",
            "Best Video Only",
            "Best Audio Only",
            "720p Video + Audio",
            "480p Video + Audio",
            "MP3 Audio Only",
            "Custom"
        ])
        default_format = self.settings.value("default_format", "Best Quality (Video + Audio)")
        self.format_combo.setCurrentText(default_format)
        form_layout.addRow("Format:", self.format_combo)

        # Options
        options_layout = QVBoxLayout()

        self.playlist_check = QCheckBox("Download entire playlist")
        self.subtitles_check = QCheckBox("Download subtitles")
        self.metadata_check = QCheckBox("Save metadata")
        self.thumbnail_check = QCheckBox("Save thumbnail")

        options_layout.addWidget(self.playlist_check)
        options_layout.addWidget(self.subtitles_check)
        options_layout.addWidget(self.metadata_check)
        options_layout.addWidget(self.thumbnail_check)

        form_layout.addRow("Options:", options_layout)

        layout.addWidget(form_frame)

        # Download button
        self.download_btn = QPushButton("Start Download")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666;
            }
        """)
        self.download_btn.clicked.connect(self._start_download)
        self.download_btn.setEnabled(False)  # Initially disabled
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

    def _create_right_panel(self) -> QWidget:
        tab_widget = QTabWidget()

        # Download Queue tab
        self.queue_widget = DownloadQueueWidget(self.download_manager)
        tab_widget.addTab(self.queue_widget, "Download Queue")

        # # Recent Downloads tab
        # recent_widget = self._create_recent_widget()
        # tab_widget.addTab(recent_widget, "Recent Downloads")

        # # Statistics tab
        # stats_widget = self._create_statistics_widget()
        # tab_widget.addTab(stats_widget, "Statistics")

        return tab_widget

    # def _create_recent_widget(self) -> QWidget:
    #     widget = QWidget()
    #     layout = QVBoxLayout(widget)

    #     # Header
    #     header = QHBoxLayout()
    #     header.addWidget(QLabel("Recently Downloaded Files"))
    #     header.addStretch()

    #     clear_btn = QPushButton("Clear All")
    #     clear_btn.clicked.connect(self._clear_recent_downloads)
    #     header.addWidget(clear_btn)

    #     layout.addLayout(header)

    #     # Recent files table
    #     self.recent_table = QTableWidget()
    #     self.recent_table.setColumnCount(4)
    #     self.recent_table.setHorizontalHeaderLabels([
    #         "File", "Size", "Date", "Actions"
    #     ])

    #     header = self.recent_table.horizontalHeader()
    #     header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    #     header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    #     header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    #     header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

    #     self.recent_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    #     self.recent_table.customContextMenuRequested.connect(self._show_recent_context_menu)

    #     layout.addWidget(self.recent_table)

    #     self._load_recent_downloads()

    #     return widget

    # def _create_statistics_widget(self) -> QWidget:
    #     widget = QWidget()
    #     layout = QVBoxLayout(widget)

    #     # Statistics groups
    #     download_stats_group = QGroupBox("Download Statistics")
    #     download_stats_layout = QGridLayout(download_stats_group)

    #     self.stats_labels = {}
    #     stats_items = [
    #         ("Total Downloads", "total_downloads"),
    #         ("Active Downloads", "active_downloads"),
    #         ("Queued Downloads", "queued_downloads"),
    #         ("Completed Downloads", "completed_downloads"),
    #     ]

    #     for i, (label, key) in enumerate(stats_items):
    #         download_stats_layout.addWidget(QLabel(f"{label}:"), i, 0)
    #         value_label = QLabel("0")
    #         value_label.setStyleSheet("font-weight: bold;")
    #         self.stats_labels[key] = value_label
    #         download_stats_layout.addWidget(value_label, i, 1)

    #     layout.addWidget(download_stats_group)

    #     # Blocking statistics
    #     blocking_stats_group = QGroupBox("Content Filter Statistics")
    #     blocking_stats_layout = QGridLayout(blocking_stats_group)

    #     blocking_items = [
    #         ("URLs Checked", "urls_checked"),
    #         ("URLs Blocked", "urls_blocked"),
    #         ("Block Rate", "block_rate"),
    #         ("Cache Hits", "cache_hits")
    #     ]

    #     for i, (label, key) in enumerate(blocking_items):
    #         blocking_stats_layout.addWidget(QLabel(f"{label}:"), i, 0)
    #         value_label = QLabel("0")
    #         value_label.setStyleSheet("font-weight: bold;")
    #         self.stats_labels[key] = value_label
    #         blocking_stats_layout.addWidget(value_label, i, 1)

    #     layout.addWidget(blocking_stats_group)

    #     # Update button
    #     update_stats_btn = QPushButton("Update Statistics")
    #     update_stats_btn.clicked.connect(self._update_statistics)
    #     layout.addWidget(update_stats_btn)

    #     layout.addStretch()
    #     return widget

    def _setup_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_download_action = QAction("&New Download", self)
        new_download_action.setShortcut(QKeySequence.StandardKey.New)
        new_download_action.triggered.connect(self._focus_url_input)
        file_menu.addAction(new_download_action)

        file_menu.addSeparator()

        # settings_action = QAction("&Settings...", self)
        # settings_action.setShortcut(QKeySequence("Ctrl+,"))
        # settings_action.triggered.connect(self._open_settings)
        # file_menu.addAction(settings_action)

        # file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        clear_url_action = QAction("&Clear URL", self)
        clear_url_action.setShortcut(QKeySequence("Ctrl+D"))
        clear_url_action.triggered.connect(lambda: self.url_input.clear())
        edit_menu.addAction(clear_url_action)

        paste_url_action = QAction("&Paste URL", self)
        paste_url_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_url_action.triggered.connect(self._paste_url)
        edit_menu.addAction(paste_url_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        theme_menu = view_menu.addMenu("&Theme")

        dark_theme_action = QAction("&Dark", self)
        dark_theme_action.triggered.connect(lambda: self._apply_theme("dark"))
        theme_menu.addAction(dark_theme_action)

        light_theme_action = QAction("&Light", self)
        light_theme_action.triggered.connect(lambda: self._apply_theme("light"))
        theme_menu.addAction(light_theme_action)

        view_menu.addSeparator()

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._refresh_all)
        view_menu.addAction(refresh_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        clear_cache_action = QAction("&Clear Cache", self)
        clear_cache_action.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Download action
        download_action = QAction("Download", self)
        download_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        download_action.triggered.connect(self._start_download)
        toolbar.addAction(download_action)

        toolbar.addSeparator()

        # Pause all action
        pause_action = QAction("Pause All", self)
        pause_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        pause_action.triggered.connect(self.download_manager.pause_all)
        toolbar.addAction(pause_action)

        # Resume all action
        resume_action = QAction("Resume All", self)
        resume_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        resume_action.triggered.connect(self.download_manager.resume_all)
        toolbar.addAction(resume_action)

        toolbar.addSeparator()

        # # Settings action
        # settings_action = QAction("Settings", self)
        # settings_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        # settings_action.triggered.connect(self._open_settings)
        # toolbar.addAction(settings_action)

    def _setup_status_bar(self):
        self.status_bar = self.statusBar()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Progress indicator for global progress
        self.global_progress = QProgressBar()
        self.global_progress.setVisible(False)
        self.global_progress.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.global_progress)

        # Download stats
        self.stats_status_label = QLabel("Downloads: 0 active")
        self.status_bar.addPermanentWidget(self.stats_status_label)

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

        # Check if URL is blocked
        if self.settings.value("enable_blocking", True, bool):
            block_result = self.blocker.is_blocked(url)
            if block_result.is_blocked:
                self.url_validation_label.setText(f"URL blocked: {block_result.details}")
                self.url_validation_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
                self.download_btn.setEnabled(False)
                return

        self.url_validation_label.setText("✓ Valid URL")
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
                action.triggered.connect(lambda checked, f=folder: self.path_input.setText(f))

        menu.exec(self.recent_paths_btn.mapToGlobal(self.recent_paths_btn.rect().bottomLeft()))

    def _start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a URL to download.")
            return

        output_path = self.path_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Warning", "Please specify an output folder.")
            return

        # Create download options
        config_options = {
            'format': self._get_format_string(),
            'writesubtitles': self.subtitles_check.isChecked(),
            'writeinfojson': self.metadata_check.isChecked(),
            'writethumbnail': self.thumbnail_check.isChecked(),
            'noplaylist': not self.playlist_check.isChecked(),
        }

        # Add to download queue
        download_id = self.download_manager.add_download(url, output_path, config_options)

        # Add to recent folders
        self.recent_folders_manager.add_folder(output_path)

        # Update UI
        self.current_download_label.setText(f"Downloading: {url[:60]}..." if len(url) > 60 else url)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Clear URL input if setting is enabled
        if self.settings.value("clear_url_after_download", True, bool):
            self.url_input.clear()

        self.status_label.setText("Download started")

    def _get_format_string(self) -> str:
        """Convert format selection to yt-dlp format string."""
        format_text = self.format_combo.currentText()
        format_map = {
            "Best Quality (Video + Audio)": "best[ext=mp4]/best",
            "Best Video Only": "best[vcodec!=none]",
            "Best Audio Only": "best[acodec!=none]",
            "720p Video + Audio": "best[height<=720][ext=mp4]/best[height<=720]",
            "480p Video + Audio": "best[height<=480][ext=mp4]/best[height<=480]",
            "MP3 Audio Only": "best[acodec!=none]/best --extract-audio --audio-format mp3"
        }
        return format_map.get(format_text, "best")

    def _on_download_started(self, url: str):
        self.status_label.setText(f"Download started: {Path(url).name}")
        self.global_progress.setVisible(True)

    def _on_download_finished(self, success: bool, message: str, file_paths: List[str]):
        self.status_label.setText(f"Download {'completed' if success else 'failed'}: {message}")

        if success and file_paths:
            # Add to recent downloads
            for file_path in file_paths:
                self.recent_manager.add(file_path)

            # Auto-open or reveal file if enabled
            if self.settings.value("auto_open", False, bool) and file_paths:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_paths[0]))
            elif self.settings.value("auto_reveal", True, bool) and file_paths:
                self._reveal_in_folder(file_paths[0])

            self._update_recent_downloads()
        else:
            QMessageBox.critical(self, "Download Error", f"Download failed: {message}")

    def _on_download_error(self, error_type: str, error_message: str):
        self.status_label.setText(f"Download error: {error_message}")
        QMessageBox.critical(self, "Download Error", f"Download failed:\n{error_message}")

    def _on_download_progress(self, download_id: str, progress_info: dict):
        progress = progress_info.get("progress", 0)
        speed = progress_info.get("speed", 0)
        eta = progress_info.get("eta")

        self.progress_bar.setValue(int(progress))

        details = f"Speed: {format_speed(speed)} | ETA: {format_duration(eta) if eta else 'Unknown'}"
        self.progress_details_label.setText(details)

    def _load_recent_downloads(self):
        recent_items = self.recent_manager.get_recent_items()
        self.recent_table.setRowCount(len(recent_items))

        for row, item in enumerate(recent_items):
            # Filename
            filename = Path(item.file_path).name if item.file_path else "Unknown"
            filename_item = QTableWidgetItem(filename)
            filename_item.setData(Qt.ItemDataRole.UserRole, item.file_path)
            self.recent_table.setItem(row, 0, filename_item)

            # Size
            try:
                size = Path(item.file_path).stat().st_size if Path(item.file_path).exists() else 0
                size_text = format_bytes(size)
            except:
                size_text = "-"
            self.recent_table.setItem(row, 1, QTableWidgetItem(size_text))

            # Date
            try:
                date_obj = datetime.fromisoformat(item.download_time)
                date_str = date_obj.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = item.download_time
            self.recent_table.setItem(row, 2, QTableWidgetItem(date_str))

            # Actions
            self.recent_table.setItem(row, 3, QTableWidgetItem("Open | Remove"))

    def _update_recent_downloads(self):
        self._load_recent_downloads()

    def _clear_recent_downloads(self):
        reply = QMessageBox.question(
            self, "Clear Recent Downloads",
            "Are you sure you want to clear all recent downloads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.recent_manager.clear()
            self._load_recent_downloads()

    def _show_recent_context_menu(self, position):
        if self.recent_table.itemAt(position) is None:
            return

        menu = QMenu(self)

        open_action = menu.addAction("Open File")
        reveal_action = menu.addAction("Show in Folder")
        menu.addSeparator()
        remove_action = menu.addAction("Remove from List")

        action = menu.exec(self.recent_table.mapToGlobal(position))

        if action == open_action:
            self._open_recent_file()
        elif action == reveal_action:
            self._reveal_recent_file()
        elif action == remove_action:
            self._remove_recent_file()

    def _open_recent_file(self):
        row = self.recent_table.currentRow()
        if row >= 0:
            item = self.recent_table.item(row, 0)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path and Path(file_path).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def _reveal_recent_file(self):
        row = self.recent_table.currentRow()
        if row >= 0:
            item = self.recent_table.item(row, 0)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                self._reveal_in_folder(file_path)

    def _remove_recent_file(self):
        row = self.recent_table.currentRow()
        if row >= 0:
            item = self.recent_table.item(row, 0)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                self.recent_manager.remove(file_path)
                self._load_recent_downloads()

    def _reveal_in_folder(self, filepath: str):
        path = Path(filepath)
        if path.exists():
            if sys.platform == "win32":
                os.startfile(path.parent)
            elif sys.platform == "darwin":
                os.system(f'open -R "{path}"')
            else:
                os.system(f'xdg-open "{path.parent}"')

    def _update_statistics(self):
        try:
            # Get download counts
            download_counts = self.download_manager.get_download_count()

            self.stats_labels["total_downloads"].setText(str(
                download_counts["active"] + download_counts["queued"] + download_counts["completed"]
            ))
            self.stats_labels["active_downloads"].setText(str(download_counts["active"]))
            self.stats_labels["queued_downloads"].setText(str(download_counts["queued"]))
            self.stats_labels["completed_downloads"].setText(str(download_counts["completed"]))

            # Get blocking statistics
            blocking_stats = self.blocker.get_statistics()

            self.stats_labels["urls_checked"].setText(str(blocking_stats.get("total_checks", 0)))
            self.stats_labels["urls_blocked"].setText(str(blocking_stats.get("blocked_requests", 0)))
            self.stats_labels["cache_hits"].setText(str(blocking_stats.get("cache_hits", 0)))

            block_rate = blocking_stats.get("block_rate", 0)
            self.stats_labels["block_rate"].setText(f"{block_rate:.1f}%")

        except Exception as e:
            QMessageBox.warning(self, "Statistics Error", f"Failed to update statistics: {str(e)}")

    def _periodic_update(self):
        # Update download statistics in status bar
        count = self.download_manager.get_download_count()
        self.stats_status_label.setText(f"Downloads: {count['active']} active")

        # Hide global progress if no active downloads
        if count['active'] == 0:
            self.global_progress.setVisible(False)
            self.progress_bar.setVisible(False)
            self.current_download_label.setText("No active download")
            self.progress_details_label.setText("")

    def _apply_theme(self, theme: str):
        self.current_theme = theme
        self.settings.setValue("theme", theme)

        try:
            import qdarktheme
            qdarktheme.setup_theme(theme)
            self.status_label.setText(f"Applied {theme} theme")
        except ImportError:
            # Apply basic styling if qdarktheme is not available
            if theme == "dark":
                self.setStyleSheet("""
                    QMainWindow { background-color: #2b2b2b; color: #ffffff; }
                    QWidget { background-color: #2b2b2b; color: #ffffff; }
                    QLineEdit { background-color: #3c3c3c; border: 1px solid #555; padding: 5px; }
                    QPushButton { background-color: #404040; border: 1px solid #555; padding: 5px; }
                    QPushButton:hover { background-color: #4a4a4a; }
                """)
            else:
                self.setStyleSheet("")  # Use system default for light theme
            self.status_label.setText(f"Applied {theme} theme (basic styling)")

    def _load_session(self):
        if self.settings.value("restore_session", True, bool):
            # Restore window geometry
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)

            # Restore last URL and path
            last_url = self.settings.value("last_url", "")
            last_path = self.settings.value("last_path", "")

            if last_url:
                self.url_input.setText(last_url)
            if last_path:
                self.path_input.setText(last_path)

    def _save_session(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("last_url", self.url_input.text())
        self.settings.setValue("last_path", self.path_input.text())

    def _focus_url_input(self):
        self.url_input.setFocus()
        self.url_input.selectAll()

    def _paste_url(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and (text.startswith("http://") or text.startswith("https://")):
            self.url_input.setText(text)

    # def _open_settings(self):
    #     dialog = SettingsDialog(self)
    #     if dialog.exec() == QDialog.DialogCode.Accepted:
    #         # Reload settings that affect the main window
    #         self._apply_theme(self.settings.value("theme", "dark"))

    #         # Update download manager settings
    #         max_concurrent = self.settings.value("max_concurrent", 3, int)
    #         self.download_manager.set_max_concurrent_downloads(max_concurrent)

    def _refresh_all(self):
        self._load_recent_downloads()
        self._update_statistics()
        self.status_label.setText("UI refreshed")

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "Clear Cache",
            "Are you sure you want to clear the application cache?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Clear blocker cache
                self.blocker.clear_statistics()

                # Cleanup missing files from recent manager
                removed = self.recent_manager.cleanup_missing_files()

                QMessageBox.information(
                    self, "Cache Cleared",
                    f"Application cache has been cleared.\nRemoved {removed} missing files from recent downloads."
                )

                self._load_recent_downloads()
                self.status_label.setText("Cache cleared")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear cache: {str(e)}")

    def _show_about(self):
        about_text = """
        <h2>YT-DLP GUI - Enhanced</h2>
        <p>Version 1.0</p>
        <p>A modern, feature-rich GUI for yt-dlp</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Multiple concurrent downloads with queue management</li>
            <li>Advanced content filtering and blocking</li>
            <li>Download history and statistics tracking</li>
            <li>Customizable themes and settings</li>
            <li>Recent folders and downloads management</li>
            <li>Progress tracking and error handling</li>
        </ul>
        <p>Built with PyQt6 and Python</p>
        <p>Integrates with yt-dlp for video downloading</p>
        """
        QMessageBox.about(self, "About YT-DLP GUI", about_text)

    def closeEvent(self, event: QCloseEvent):
        # Save session
        self._save_session()

        # Check if downloads are active
        count = self.download_manager.get_download_count()
        if count['active'] > 0:
            reply = QMessageBox.question(
                self, "Active Downloads",
                f"There are {count['active']} active downloads.\n"
                "Do you want to close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                # Cancel all active downloads
                self.download_manager.cancel_all()

        # Stop timers
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()

        if hasattr(self, 'queue_widget') and hasattr(self.queue_widget, 'update_timer'):
            self.queue_widget.update_timer.stop()

        # Stop download manager
        self.download_manager.stop_manager()

        # Accept the close event
        event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("YT-DLP GUI Enhanced")
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
