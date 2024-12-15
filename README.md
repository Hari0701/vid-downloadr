# Media Downloader

A powerful, user-friendly application for downloading media content from popular social platforms.

## Table of Contents

- [Overview](#overview)
- [Usage Guide](#usage-guide)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Setup](#setup)
- [Disclaimer](#disclaimer)


## Overview

The Media Downloader is a sophisticated, cross-platform application designed to streamline the process of downloading media content from various Media Downloader platforms. Built with Python and featuring a modern, intuitive GUI, this toolkit empowers users to easily archive and manage their favorite online content.


## Usage Guide

### Adding Content:

- Paste the media URL into the input field.
- Click "Add" and provide a custom name if desired.
- (Downloading instagram media requires being logged in with the Instagram Login button)

### Customizing Save Location:

- Access the file browser via "Manage Files".
- Navigate and set your preferred download directory.

### Monitoring Downloads:

- Track overall progress via the status label and progress bar.
- Check individual download statuses in the download list.

## Advanced Features

### YouTube Enhancements

- Quality selection (360p to 1080p)
- Playlist support
- Audio extraction capability

### Instagram Capabilities

- Support for posts, reels, and carousels
- Caption preservation

### Twitter Integration

- Download images and videos from tweets

### Pinterest Functionality

- High-quality image retrieval from pins and boards
- Automated file naming based on pin content

## Setup

To get started with Media Fetcher, follow these steps:

### Prerequisites

- **Python 3.x**: Ensure you have Python 3.x installed on your system. You can download it from [python.org](https://www.python.org/).
- **Git**: Install Git if you haven't already, to clone the repository. Download it from [git-scm.com](https://git-scm.com/).
- **FFmpeg**: Install FFmpeg for media processing. You can install it using the following command (for Windows users with winget):

  ```bash
  winget install "FFmpeg (Essentials Build)"
  ```

### Installation

1. **Clone the Repository:**

   Open your terminal or command prompt and run the following command to clone the repository:

   ```bash
   git clone https://github.com/Hari0701/vid-downloadr.git
   ```

2. **Navigate to the Project Directory:**

   Change into the project directory:

   ```bash
   cd vid-downloadr
   ```

3. **Install Dependencies:**

   Use pip to install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

- **Start the Application:**

  Run the application using the following command:

  ```bash
  python main.py
  ```

### Troubleshooting

- If you encounter any issues during setup, ensure all dependencies are installed correctly and check for any error messages in the terminal.

This setup guide provides a clear path for users to install and configure your application, ensuring they can get it up and running smoothly. Adjust the instructions as needed to fit the specifics of your project.

## Disclaimer
```text
    The Media Downloader Toolkit is intended for personal use only. 
    Users are responsible for adhering to the terms of service of the respective platforms and all applicable copyright laws. 
    The developers assume no liability for misuse of this software.
    Your Instagram account may be banned if you use this tool for unauthorized purposes or too much usage it is always recommended to use it with caution and create a new account for testing purposes.'
```
