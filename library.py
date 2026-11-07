import json
import re
import sqlite3
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent


def play_duplicate_alert():
	try:
		import pygame
	except ImportError:
		return
	try:
		if not pygame.mixer.get_init():
			pygame.mixer.init()
		pygame.mixer.Sound(str(SCRIPT_DIR / "beeping_for_book_scanner.wav")).play()
	except (pygame.error, OSError):
		pass  # The printed alert still works without audio.


def is_valid_isbn(isbn):
	if re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
		check_digit = 10 if isbn[-1] == "X" else int(isbn[-1])
		return (sum((10 - i) * int(digit) for i, digit in enumerate(isbn[:-1])) + check_digit) % 11 == 0
	if re.fullmatch(r"97[89][0-9]{10}", isbn):
		return sum((1, 3)[i % 2] * int(digit) for i, digit in enumerate(isbn)) % 10 == 0
	return False


def lookup_book(isbn):
	query = urlencode({
		"q": f"isbn:{isbn}",
		"fields": "title,author_name,editions,editions.title",
		"limit": 1,
	})
	request = Request(
		f"https://openlibrary.org/search.json?{query}",
		headers={"User-Agent": "library-cli (https://github.com/elgiad007/library-cli)"},
	)
	with urlopen(request, timeout=10) as response:
		docs = json.load(response)["docs"]
	if not isinstance(docs, list):
		raise ValueError("Unexpected Open Library response")
	if not docs:
		return None

	book = docs[0]
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
	return f"{title} — {author if author and author != 'NIL' else 'Unknown author'}"


def show_books(rows):
	for isbn, title, author in rows:
		print(f"{book_label(title, author)}")
		if isbn and isbn != "NIL":
			print(f"  ISBN: {isbn}")
	print(f"{len(rows)} {'book' if len(rows) == 1 else 'books'} found.")


def add_book(con, isbn="NIL"):
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
	duplicate = con.execute(
		"SELECT isbn, title, author FROM books WHERE title = ? COLLATE NOCASE AND author = ? COLLATE NOCASE LIMIT 1;",
		(title, author),
	).fetchone()
	if duplicate:
		print(f"Already in library: {book_label(duplicate[1], duplicate[2])}")
		play_duplicate_alert()
		if input("Add another copy? [y/N]: ").strip().lower() != "y":
			return
	with con:
		con.execute("INSERT INTO books (isbn, title, author) VALUES (?, ?, ?);", (isbn, title, author))
	print(f"Added: {book_label(title, author)}")


def scan(con):
	print("Scan an ISBN, or type back.")
	while True:
		usr_input = input("scan> ").strip()
		if usr_input.lower() == "back":
			break
		if not usr_input:
			continue

		isbn = usr_input.replace("-", "").replace(" ", "").upper()
		if not is_valid_isbn(isbn):
			print("Invalid ISBN. Check the number and try again.")
			continue

		duplicate = con.execute("SELECT title, author FROM books WHERE isbn = ? COLLATE NOCASE LIMIT 1;", (isbn,)).fetchone()
		if duplicate:
			print(f"Already in library: {book_label(*duplicate)}")
			play_duplicate_alert()
			continue

		print(f"Looking up {isbn}…")
		try:
			book = lookup_book(isbn)
		except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
			print("Could not reach Open Library. Try again, or use add to enter the book manually.")
			continue
		if book is None:
			print(f"No book details found for ISBN {isbn}.")
			if input("Add manually? [y/N]: ").strip().lower() == "y":
				add_book(con, isbn)
			continue

		title, author = book
		with con:
			con.execute("INSERT INTO books (isbn, title, author) VALUES (?, ?, ?);", (isbn, title, author))
		print(f"Added: {book_label(title, author)}")


def main(con):
	count = con.execute("SELECT COUNT(*) FROM books;").fetchone()[0]
	print(f"Library · {count} {'book' if count == 1 else 'books'}")
	print("Commands: scan, add, search, list, count, help, exit")
	while True:
		usr_input = input("library> ").strip()
		if not usr_input:
			continue
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
				escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
				pattern = f"%{escaped}%"
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
			print(f"Catalog error: {error}")
	
if __name__ == "__main__":
	with closing(sqlite3.connect(SCRIPT_DIR / "isbn.db")) as con:
		con.execute("CREATE TABLE IF NOT EXISTS books (isbn TEXT, title TEXT, author TEXT);")
		main(con)
