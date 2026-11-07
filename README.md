# Library CLI

Run `python library.py` from the project folder on Windows, or `python3 library.py`
on macOS or Raspberry Pi OS. Use Python 3.8 or newer. The command line and SQLite
database work with Python's standard library. ISBN lookups need internet access
to Open Library.

At the `library>` prompt, use `scan`, `add`, `search <text>`, `list`, `count`,
`help`, or `exit`. `search` matches ISBNs, titles, and authors; without text it
prompts for a query. The older `entermanually`, `printall`, and `countall`
commands still work.

In `scan`, scan a barcode or type an ISBN-10 or ISBN-13 and press Enter. A
scanner that sends Enter after each barcode submits it automatically. Type
`back` to return to the main prompt. If Open Library has no details for an
ISBN, the app offers manual entry while retaining that ISBN. In `add`, press
Enter at the author prompt if the author is unknown, or type `back` to cancel.
When a title and author already exist, the app asks before adding another copy.

The app reads and writes `isbn.db` beside `library.py`, even when you launch it
from another folder. To use an existing catalog, place its database there before
starting the script. If the file is absent, the app creates an empty catalog.

Duplicate scans always show a message. For an audible alert, install `pygame`
in the Python environment you use to run the app and keep
`beeping_for_book_scanner.wav` beside the script.
