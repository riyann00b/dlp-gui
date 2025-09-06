import sys
from pathlib import Path
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
import qdarktheme

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from Ui.main_window import MainWindow as YTDLPGui
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all required modules are available")
    sys.exit(1)


def setup_application():
    """Setup application properties and theme."""
    app = QApplication(sys.argv)

    # Application metadata
    app.setApplicationName("YT-DLP GUI Enhanced")
    app.setApplicationDisplayName("YT-DLP GUI")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("riyanoob")
    app.setOrganizationDomain("github.com/riyanoob")

    # Set application icon (if available)
    icon_path = project_root / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply custom theme
    try:
        qdarktheme.setup_theme(
            "dark",
            custom_colors={
                "primary": "#7aa2f7",
                "background": "#1a1b26",
            },
            corner_shape="rounded",
            additional_qss="""
            QMainWindow {
                background-color: #1a1b26;
            }
            QFrame[frameShape="4"] {
                color: #565f89;
            }
            QPushButton {
                font-weight: 500;
            }
            QTabWidget::pane {
                border: 1px solid #565f89;
                border-radius: 6px;
            }
            QTabBar::tab {
                border-radius: 4px;
                margin: 2px;
            }
            """
        )
    except Exception as e:
        print(f"Theme setup failed: {e}")
        # Fallback to default theme
        app.setStyleSheet("")

    # Set default font
    try:
        # Try to use Inter font, fallback to system fonts
        fonts_to_try = ["Inter", "Segoe UI", "SF Pro Display", "Ubuntu", "Arial"]
        for font_name in fonts_to_try:
            font = QFont(font_name, 10)
            if font.exactMatch():
                app.setFont(font)
                break
        else:
            # Use default system font with size 10
            font = app.font()
            font.setPointSize(10)
            app.setFont(font)
    except Exception as e:
        print(f"Font setup failed: {e}")

    # Enable high DPI scaling (PyQt6 compatible attributes)
    try:
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    except AttributeError:
        # These attributes might not be available in all PyQt6 versions
        pass

    try:
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        # Fallback for newer PyQt6 versions where this is default
        pass

    return app


def check_dependencies():
    """Check if all required dependencies are available."""
    missing_deps = []

    # Check for required modules
    required_modules = [
        'yt_dlp',
        'PyQt6',
        'qdarktheme'
    ]

    for module in required_modules:
        try:
            __import__(module.replace('-', '_'))
        except ImportError:
            missing_deps.append(module)

    if missing_deps:
        error_msg = "Missing required dependencies:\n" + "\n".join(f"- {dep}" for dep in missing_deps)
        error_msg += "\n\nPlease install them using:\npip install " + " ".join(missing_deps)

        print(error_msg)

        # Show GUI error if PyQt6 is available
        if 'PyQt6' not in missing_deps:
            QApplication(sys.argv)
            QMessageBox.critical(None, "Missing Dependencies", error_msg)

        return False

    return True

def main():
    """Main application entry point."""
    print("Starting YT-DLP GUI Enhanced...")

    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)

    # Create application
    try:
        app = setup_application()
    except Exception as e:
        print(f"Failed to setup application: {e}")
        sys.exit(1)

    # Create and show main window
    try:
        print("Initializing main window...")
        window = YTDLPGui()

        # Center window on screen
        screen = app.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = window.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            window.move(window_geometry.topLeft())

        window.show()
        print("Application ready!")

        # Run the application event loop
        exit_code = app.exec()
        print(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        error_msg = f"Failed to initialize main window: {str(e)}"
        print(error_msg)

        # Show error dialog
        try:
            QMessageBox.critical(None, "Startup Error",
                               f"{error_msg}\n\nPlease check the console for more details.")
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()
