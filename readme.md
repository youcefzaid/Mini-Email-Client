![Alt text](/screenshot.png "Mini Email Client screenshot")
# Mini Email Client

A simple, read-only email client built with Python, GTK 4 and Adwaita.

## Features

- IMAP email retrieval
- Login with email and password
- View inbox emails
- Search functionality
- Email content display
- Pagination for email list

## Requirements

- Python 3.x
- GTK 4.0
- PyGObject

## Setup

1. Install required libraries:
   ```
   pip3 install PyGObject
   ```

2. Ensure GTK 4.0 is installed on your system.

3. Add you own servers to the `config.json` file in the same directory as the script with IMAP server configurations.

## Usage

Run the script:
   ```
   python3 main.py
   ```
