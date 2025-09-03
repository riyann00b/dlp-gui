from PyQt6.QtCore import QThread, pyqtSignal
from Core.downloader import Downloader


class DownloadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, url: str, output_path: str, config_options: dict):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.config_options = config_options
        self.downloader = Downloader()

    def run(self):
        try:
            success = self.downloader.download(
                self.url,
                self.output_path,
                self.config_options,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(success, "Download completed successfully!" if success else "Download failed!")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")
