import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QComboBox, QLabel, QProgressBar,
    QCheckBox, QFileDialog, QMessageBox, QFrame, QStyle, QSizePolicy, QListWidget, QListWidgetItem
)

from Core.blocker import ContentBlocker
from Core.config import YTDLPConfig
from Core.logger import ActivityLogger
from Ui.threads import DownloadThread
import qdarktheme


class YTDLPGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.blocker = ContentBlocker()
        self.config = YTDLPConfig()
        self.logger = ActivityLogger()
        self.download_thread: DownloadThread | None = None

        self.setWindowTitle("YT-DLP GUI")
        self.setMinimumSize(960, 640)
        self._build_ui()
        self.statusBar().showMessage("Ready")

    def _add_recent_download(self, file_path: str):
        """Add a file to the Recent Downloads list (newest on top, keep max 10)."""
        item = QListWidgetItem(file_path)
        self.recent_list.insertItem(0, item)

        # Limit to last 10 downloads
        if self.recent_list.count() > 10:
            self.recent_list.takeItem(self.recent_list.count() - 1)

    def _download_finished(self, success: bool, message: str):
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.statusBar().showMessage("Download completed!")
            QMessageBox.information(self, "Success", message)

            # Add the downloaded file/folder to Recent Downloads
            self._add_recent_download(self.path_input.text())
        else:
            self.statusBar().showMessage("Download failed!")
            QMessageBox.critical(self, "Error", message)

        self.logger.log_activity(message)


    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Title Bar
        header = QHBoxLayout()
        title = QLabel("YT-DLP Downloader")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Theme switcher
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText("dark")
        self.theme_combo.currentTextChanged.connect(self._apply_theme)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("Theme:"))
        header.addWidget(self.theme_combo)
        root.addLayout(header)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(divider)

        # Form Card
        form_card = QFrame()
        form_card.setObjectName("card")
        form_card.setStyleSheet("""
            QFrame#card {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
            }
        """)
        form_layout_outer = QVBoxLayout(form_card)
        form_layout_outer.setContentsMargins(16, 16, 16, 16)
        form_layout_outer.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        # URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter video / playlist URL…")
        form.addRow("URL:", self.url_input)

        # Output path
        path_row = QHBoxLayout()
        self.path_input = QLineEdit(os.path.expanduser("~/Downloads"))
        browse_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setIcon(browse_icon)
        self.browse_btn.clicked.connect(self._browse_folder)
        path_row.addWidget(self.path_input)
        path_row.addWidget(self.browse_btn)
        path_row_w = QWidget()
        path_row_w.setLayout(path_row)
        form.addRow("Output:", path_row_w)

        # Format
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Best Quality (Video + Audio)",
            "Best Video Only",
            "Best Audio Only",
            "720p Video + Audio",
            "480p Video + Audio",
            "MP3 Audio Only",
            "Custom",
        ])
        form.addRow("Format:", self.format_combo)

        # Options
        toggles_row = QHBoxLayout()
        self.playlist_check = QCheckBox("Download playlist")
        self.subtitles_check = QCheckBox("Download subtitles")
        toggles_row.addWidget(self.playlist_check)
        toggles_row.addWidget(self.subtitles_check)
        toggles_row.addStretch(1)
        form.addRow("Options:", toggles_row)

        form_layout_outer.addLayout(form)

        # Download button
        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        download_pix = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.download_btn = QPushButton("Download")
        self.download_btn.setIcon(download_pix)
        self.download_btn.clicked.connect(self._start_download)
        actions_row.addWidget(self.download_btn)
        form_layout_outer.addLayout(actions_row)

        root.addWidget(form_card)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        root.addWidget(self.progress_bar)

        # Toolbar
        self._build_toolbar()

        recent_card = QFrame()
        recent_card.setObjectName("card")
        recent_card.setStyleSheet("""
            QFrame#card {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
            }
        """)
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(12, 12, 12, 12)
        recent_layout.setSpacing(6)

        recent_label = QLabel("Recently Downloaded")
        recent_label.setStyleSheet("font-weight: 600;")
        recent_layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(180)
        self.recent_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        recent_layout.addWidget(self.recent_list)

        root.addWidget(recent_card)

    # ---------- Toolbar ----------
    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)

        open_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        act_browse = QAction(open_icon, "Browse Output Folder", self)
        act_browse.triggered.connect(self._browse_folder)
        tb.addAction(act_browse)

        save_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        act_download = QAction(save_icon, "Start Download", self)
        act_download.triggered.connect(self._start_download)
        tb.addAction(act_download)

    # ---------- Helpers ----------
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.path_input.text())
        if folder:
            self.path_input.setText(folder)

    def _apply_theme(self, theme: str):
        qdarktheme.setup_theme(
            theme,
            custom_colors={"primary": "#7aa2f7"},
            corner_shape="rounded",
        )

    def _start_download(self):
        url = self.url_input.text().strip()
        output_path = self.path_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a URL.")
            return

        if not output_path:
            QMessageBox.warning(self, "Missing Output Folder", "Please select an output folder.")
            return

        if self.blocker.is_blocked(url):
            QMessageBox.critical(self, "Blocked", "This URL is blocked by content filter!")
            return

        format_selection = self.format_combo.currentText()
        config_options = self.config.get_config(format_selection)
        if self.playlist_check.isChecked():
            config_options.update(self.config.get_playlist_config())
        if self.subtitles_check.isChecked():
            config_options.update(self.config.get_subtitle_config())

        self.download_thread = DownloadThread(url, output_path, config_options)
        self.download_thread.progress.connect(lambda msg: self.logger.log_activity(msg))
        self.download_thread.finished.connect(self._download_finished)

        # UI state
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.statusBar().showMessage("Downloading…")

        self.logger.log_activity(f"Starting download: {url}")
        self.download_thread.start()
