# These standard-library modules handle JSON data, text patterns, and a local
# SQLite database. Python includes them, so no separate installation is needed.
import json
import re
import sqlite3
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# __file__ is this script's path. resolve() makes it absolute, and parent finds
# its folder so the database and sound can be found from any working directory.
SCRIPT_DIR = Path(__file__).resolve().parent


def play_duplicate_alert():
	"""Play a warning sound if the optional pygame package and audio work."""
	try:
		# Import here so missing pygame does not prevent the main program running.
		import pygame
	except ImportError:
		# return without a value ends the function and gives the caller None.
		return
	try:
		if not pygame.mixer.get_init():
			pygame.mixer.init()
		pygame.mixer.Sound(str(SCRIPT_DIR / "beeping_for_book_scanner.wav")).play()
	except (pygame.error, OSError):
		pass  # The printed alert still works without audio.


def is_valid_isbn(isbn):
	"""Check the format and checksum of an ISBN-10 or ISBN-13 string."""
	# fullmatch checks the whole string. {9} means nine repetitions; [0-9X]
	# allows a digit or X. The r prefix keeps backslashes literal in regex text.
	if re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
		# Negative indexes count from the end. ISBN-10 uses X to represent ten.
		check_digit = 10 if isbn[-1] == "X" else int(isbn[-1])
		# isbn[:-1] excludes the last character. enumerate yields each position
		# and digit; sum adds the weighted digits. % is the remainder operator:
		# a valid ISBN-10 checksum is divisible by 11 (remainder zero).
		return (sum((10 - i) * int(digit) for i, digit in enumerate(isbn[:-1])) + check_digit) % 11 == 0
	if re.fullmatch(r"97[89][0-9]{10}", isbn):
		# ISBN-13 starts with 978 or 979. i % 2 alternates between 0 and 1,
		# selecting weights 1 and 3 from the tuple; the total must divide by 10.
		return sum((1, 3)[i % 2] * int(digit) for i, digit in enumerate(isbn)) % 10 == 0
	return False


def lookup_book(isbn):
	"""Return a (title, author) tuple from Open Library, or None if not found."""
	# A dictionary holds named query options. urlencode turns it into text
	# suitable for a URL, escaping characters that have special meanings there.
	query = urlencode({
		"q": f"isbn:{isbn}",
		"fields": "title,author_name,editions,editions.title",
		"limit": 1,
	})
	request = Request(
		f"https://openlibrary.org/search.json?{query}",
		headers={"User-Agent": "library-cli (https://github.com/elgiad007/library-cli)"},
	)
	# with closes the response even if reading fails. The timeout limits waiting
	# on network operations; json.load converts JSON into Python lists/dicts.
	with urlopen(request, timeout=10) as response:
		docs = json.load(response)["docs"]
	if not isinstance(docs, list):
		# raise reports invalid data to the caller, which can catch the error.
		raise ValueError("Unexpected Open Library response")
	if not docs:
		# Empty lists are false in an if condition.
		return None

	book = docs[0]
	# get supplies a default when a dictionary key is missing. Prefer the
	# matching edition's title, falling back to the broader book record.
	editions = book.get("editions", {}).get("docs", [])
	title = editions[0].get("title") if editions else None
	title = title or book.get("title")
	if not isinstance(title, str) or not title.strip():
		return None
	authors = book.get("author_name") or []
	if not isinstance(authors, list) or (authors and not isinstance(authors[0], str)):
		raise ValueError("Unexpected author data from Open Library")
	return title, authors[0] if authors else "NIL"


def book_label(title, author):
	"""Build the display label, translating the stored NIL placeholder."""
	# An f-string inserts expressions inside braces into the resulting text.
	return f"{title} — {author if author and author != 'NIL' else 'Unknown author'}"


def show_books(rows):
	"""Print query results and a count with singular/plural wording."""
	# Tuple unpacking assigns each row's three values to descriptive names.
	for isbn, title, author in rows:
		print(f"{book_label(title, author)}")
		if isbn and isbn != "NIL":
			print(f"  ISBN: {isbn}")
	print(f"{len(rows)} {'book' if len(rows) == 1 else 'books'} found.")


def add_book(con, isbn="NIL"):
	"""Ask for book details and store them using the database connection con."""
	# isbn has a default for manual entry; scan can supply an actual ISBN.
	# input returns text, and strip removes whitespace at either end.
	title = input("Title (or back): ").strip()
	if title.lower() == "back":
		return
	if not title:
		print("Title is required. Nothing added.")
		return
	author = input("Author (optional, or back): ").strip()
	if author.lower() == "back":
		return
	author = author or "NIL"
	# ? placeholders bind values separately from SQL, safely handling user
	# text such as apostrophes. COLLATE NOCASE ignores ASCII letter case.
	# fetchone returns one matching row, or None when there is no match.
	duplicate = con.execute(
		"SELECT isbn, title, author FROM books WHERE title = ? COLLATE NOCASE AND author = ? COLLATE NOCASE LIMIT 1;",
		(title, author),
	).fetchone()
	if duplicate:
		print(f"Already in library: {book_label(duplicate[1], duplicate[2])}")
		play_duplicate_alert()
		if input("Add another copy? [y/N]: ").strip().lower() != "y":
			return
	# A connection's with block commits a successful transaction or rolls it
	# back on error. Unlike closing() below, it does not close the connection.
	with con:
		con.execute("INSERT INTO books (isbn, title, author) VALUES (?, ?, ?);", (isbn, title, author))
	print(f"Added: {book_label(title, author)}")


def scan(con):
	"""Keep accepting ISBNs until the user types back."""
	print("Scan an ISBN, or type back.")
	# while True repeats indefinitely: break exits; continue skips the rest
	# of the current iteration and starts the next prompt.
	while True:
		usr_input = input("scan> ").strip()
		if usr_input.lower() == "back":
			break
		if not usr_input:
			continue

		# Normalize common ISBN formatting before validation and lookup.
		isbn = usr_input.replace("-", "").replace(" ", "").upper()
		if not is_valid_isbn(isbn):
			print("Invalid ISBN. Check the number and try again.")
			continue

		# The comma makes (isbn,) a one-item tuple for the SQL parameters.
		duplicate = con.execute("SELECT title, author FROM books WHERE isbn = ? COLLATE NOCASE LIMIT 1;", (isbn,)).fetchone()
		if duplicate:
			# * unpacks the row into separate title and author arguments.
			print(f"Already in library: {book_label(*duplicate)}")
			play_duplicate_alert()
			continue

		print(f"Looking up {isbn}…")
		try:
			book = lookup_book(isbn)
		except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
			# Catch network and response-data failures so scanning can continue.
			print("Could not reach Open Library. Try again, or use add to enter the book manually.")
			continue
		if book is None:
			print(f"No book details found for ISBN {isbn}.")
			if input("Add manually? [y/N]: ").strip().lower() == "y":
				add_book(con, isbn)
			continue

		title, author = book
		# Save the successful lookup as one database transaction.
		with con:
			con.execute("INSERT INTO books (isbn, title, author) VALUES (?, ?, ?);", (isbn, title, author))
		print(f"Added: {book_label(title, author)}")


def main(con):
	"""Run the command prompt and dispatch each command to its operation."""
	# COUNT(*) returns one row with one value; [0] extracts that value.
	count = con.execute("SELECT COUNT(*) FROM books;").fetchone()[0]
	print(f"Library · {count} {'book' if count == 1 else 'books'}")
	print("Commands: scan, add, search, list, count, help, exit")
	while True:
		usr_input = input("library> ").strip()
		if not usr_input:
			continue
		# partition splits at the first space, preserving the rest as an
		# argument. _ is a conventional name for a value we do not need.
		command, _, argument = usr_input.partition(" ")
		command = command.lower()
		try:
			if command == "scan" and not argument.strip():
				scan(con)
			elif command in ("add", "entermanually") and not argument.strip():
				add_book(con)
			elif command == "search":
				query = argument.strip() or input("Search: ").strip()
				if not query or query.lower() == "back":
					continue
				# SQL LIKE treats % and _ as wildcards. Escape the user's versions
				# to search for them literally, then add % around the whole query
				# to match text anywhere in a field. SQL parameters alone do not
				# escape LIKE wildcards. Backslashes are doubled in Python strings.
				escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
				pattern = f"%{escaped}%"
				# fetchall collects every matching row into a list; ORDER BY
				# sorts the results before they are displayed.
				rows = con.execute(
					"SELECT isbn, title, author FROM books WHERE isbn LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\' ORDER BY title COLLATE NOCASE, author COLLATE NOCASE;",
					(pattern, pattern, pattern),
				).fetchall()
				if rows:
					show_books(rows)
				else:
					print(f'No books found for "{query}".')
			elif command in ("list", "printall") and not argument.strip():
				rows = con.execute("SELECT isbn, title, author FROM books ORDER BY title COLLATE NOCASE, author COLLATE NOCASE;").fetchall()
				if rows:
					show_books(rows)
				else:
					print("Library is empty. Use scan or add to start.")
			elif command in ("count", "countall") and not argument.strip():
				count = con.execute("SELECT COUNT(*) FROM books;").fetchone()[0]
				print(f"{count} {'book' if count == 1 else 'books'}.")
			elif command == "help" and not argument.strip():
				print("Commands: scan, add, search <text>, list, count, help, exit")
				print("In scan or add, type back to cancel or return.")
			elif command == "exit" and not argument.strip():
				break
			else:
				print(f'Unknown command: "{usr_input}". Type help for commands.')
		except sqlite3.Error as error:
			# Keep the prompt running after a database error; `as error` lets
			# us include the exception's explanation in the message.
			print(f"Catalog error: {error}")
	
# This guard runs startup only when the file is executed directly, not when
# another module (such as the tests) imports its functions.
if __name__ == "__main__":
	# SQLite creates the database file if needed. closing guarantees the
	# connection closes when this block ends, including when an error occurs.
	with closing(sqlite3.connect(SCRIPT_DIR / "isbn.db")) as con:
		# IF NOT EXISTS preserves an existing table and its saved books.
		con.execute("CREATE TABLE IF NOT EXISTS books (isbn TEXT, title TEXT, author TEXT);")
		main(con)
