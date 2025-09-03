# DLP GUI - A Desktop Frontend for yt-dlp

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg) ![Python Version](https://img.shields.io/badge/python-3.9+-brightgreen.svg) ![Framework: PyQt6](https://img.shields.io/badge/Framework-PyQt6-orange.svg)

A clean, modern, and user-friendly desktop application for downloading video and audio using the powerful `yt-dlp` library. This project provides an intuitive graphical interface, eliminating the need to use the command line for your daily download needs.

<!-- 
**IMPORTANT**: Replace the image below with a screenshot of your application!
A good screenshot is the most effective way to show what your project does.
![dlp-gui screenshot](https://user-images.githubusercontent.com/12530799/208338902-3162b5b3-a335-4927-995a-e160689886a8.png)
-->

## About The Project

`dlp-gui` is built for users who want the power and versatility of `yt-dlp` without the complexity of command-line arguments. It wraps the core functionality of `yt-dlp` in a simple interface, allowing you to download videos, audio, playlists, and subtitles with just a few clicks. The application is designed with a clear separation between the core download engine and the user interface, making it robust and extensible.

## Key Features

*   **Simple Interface**: Just paste a URL, choose your settings, and click download.
*   **Flexible Format Selection**: Download in various formats, including:
    *   Best Quality Video + Audio (up to 1080p)
    *   High-quality MP3 Audio
    *   720p / 480p standard video
    *   Video-only or Audio-only tracks
*   **Playlist & Subtitle Support**: Download entire playlists and include subtitles with a single checkbox.
*   **Built-in Content Blocker**: An optional, pre-configured filter to block adult content URLs.
*   **Modern Theme**: A beautiful dark/light theme powered by `qdarktheme` that looks great on any OS.
*   **Recent Downloads History**: Quickly see a list of your last 10 completed downloads.

## Getting Started

Follow these steps to get a local copy up and running.

### Prerequisites

You will need the following software installed on your system:
*   **Python 3.9+**
*   **FFmpeg**: `yt-dlp` requires FFmpeg to merge video and audio files (like for MP4) and to create MP3s.
    *   **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` directory to your system's PATH.
    *   **macOS**: `brew install ffmpeg`
    *   **Linux (Debian/Ubuntu)**: `sudo apt update && sudo apt install ffmpeg`

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/riyann00b/dlp-gui.git
    cd dlp-gui
    ```

2.  **Create and activate a virtual environment.** You can use either Python's built-in `venv` or the faster `uv`.

    *   **Option A: Using `uv` (Recommended)**
        ```sh
        # Create the virtual environment
        uv venv
        
        # Activate it (the command is the same as for venv)
        # On Windows (Git Bash or WSL):
        source .venv/bin/activate
        # On macOS / Linux:
        source .venv/bin/activate
        # On Windows (Command Prompt/PowerShell):
        .\.venv\Scripts\activate
        ```

    *   **Option B: Using standard `venv`**
        ```sh
        # Create the virtual environment
        # On Windows:
        python -m venv .venv
        # On macOS / Linux:
        python3 -m venv .venv
        
        # Activate it
        # On Windows (Git Bash or WSL):
        source .venv/bin/activate
        # On macOS / Linux:
        source .venv/bin/activate
        # On Windows (Command Prompt/PowerShell):
        .\.venv\Scripts\activate
        ```

3.  **Install the required Python packages.**

    *   **If you are using `uv`:**
        ```sh
        uv pip install PyQt6 pyqtdarktheme yt-dlp
        ```

    *   **If you are using `pip`:**
        ```sh
        pip install PyQt6 pyqtdarktheme yt-dlp
        ```

### Running the Application

Once the installation is complete, you can run the application with a single command:

```sh
python main.py
```

## How to Use

1.  **Enter URL**: Paste the video or playlist URL into the "URL" input field.
2.  **Choose Output**: Select the folder where you want to save your files. It defaults to your system's "Downloads" folder.
3.  **Select Format**: Choose the desired video/audio quality from the "Format" dropdown.
4.  **Set Options**: Check the "Download playlist" or "Download subtitles" boxes if needed.
5.  **Download**: Click the "Download" button to start the process. Progress will be shown in the status bar and with a progress bar.

## Project Structure

The project is organized with a clear separation of concerns:

```
└── riyann00b-dlp-gui/
    ├── main.py               # Application entry point
    ├── Core/                 # Backend logic (downloader, config, etc.)
    │   ├── blocker.py
    │   ├── config.py
    │   ├── downloader.py
    │   └── logger.py
    └── Ui/                   # PyQt6 user interface files
        ├── main_window.py
        └── threads.py
```

*   **`Core/`**: Contains all the business logic. It has no knowledge of the UI, which means it could be reused for a command-line tool or a web server in the future.
*   **`Ui/`**: Contains all the PyQt6 widgets, windows, and threading logic needed to create the graphical interface.

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## License

Distributed under the MIT License.

## Acknowledgments

*   [yt-dlp Team](https://github.com/yt-dlp/yt-dlp) for creating and maintaining the incredible download library.
*   [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the robust GUI framework.
*   [QDarkTheme](https://github.com/5yutan5/PyQt-dark-theme) for the beautiful dark/light theme.
