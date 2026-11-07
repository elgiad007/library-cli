# Library CLI

Run `python library.py` from the project folder on Windows, or `python3 library.py`
on macOS or Raspberry Pi OS. Use Python 3.8 or newer. The command line and SQLite
database work with Python's standard library. ISBN lookups need internet access
to Open Library.

Choose `scan`, then scan a barcode or type an ISBN-10 or ISBN-13 and press Enter.
A scanner that sends Enter after each barcode submits it automatically. Type
`exit` to return to the main menu. If a book isn't listed in Open Library, use
`entermanually` from the main menu.

The app reads and writes `isbn.db` beside `library.py`, even when you launch it
from another folder. To use an existing catalog, place its database there before
starting the script. If the file is absent, the app creates an empty catalog.

Duplicate scans always show a message. For an audible alert, install `pygame`
in the Python environment you use to run the app and keep
`beeping_for_book_scanner.wav` beside the script.
