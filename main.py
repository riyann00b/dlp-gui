import sys
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
import qdarktheme

from Ui.main_window import YTDLPGui


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DLP GUI")
    app.setOrganizationName("riyanoob")

    # Apply theme
    qdarktheme.setup_theme(
        "dark",
        custom_colors={"primary": "#7aa2f7"},
        corner_shape="rounded",
    )

    # Default font
    app.setFont(QFont("Inter", 10))

    # Launch main window
    win = YTDLPGui()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
