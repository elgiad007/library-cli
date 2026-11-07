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


def scan(con):
	while True:
		usr_input = input("scan or exit: ").strip()
		if usr_input.lower() == "exit":
			break

		isbn = usr_input.replace("-", "").replace(" ", "").upper()
		if not is_valid_isbn(isbn):
			print("ERROR: Invalid ISBN number. Please try again.")
			continue

		if con.execute("SELECT 1 FROM books WHERE isbn = ? COLLATE NOCASE;", (isbn,)).fetchone():
			print("\nBook already added.\n")
			play_duplicate_alert()
			continue

		try:
			book = lookup_book(isbn)
		except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError) as error:
			print(f"ERROR: Open Library lookup failed ({error}). Try scanning again.")
			continue
		if book is None:
			print(f"No book details found for ISBN {isbn}. You can add it with 'entermanually'.")
			continue

		title, author = book
		with con:
			con.execute("INSERT INTO books (isbn, title, author) VALUES (?, ?, ?);", (isbn, title, author))
		print(f"{title}, {author}")


def main(con):
	cur = con.cursor()
	
	while True:
		print("\n______________________________\nCommands:\n\n'scan'\n'entermanually'\n'search'\n'printall'\n'countall'\n'exit'\n\n")
		
		usr_input = input("Type cmd: ")
		
		try:
			if usr_input.lower() == "scan":
				scan(con)
			elif usr_input.lower() == "entermanually":
				usr_input = input("Enter book title with correct caps: ")
				
				res = cur.execute("SELECT title FROM books WHERE title = ?;", (usr_input.lower(),))
				copys = res.fetchall()
				
				for copy in copys:
					print("\nBook already added.\n")
					play_duplicate_alert()
					continue
				book_title = usr_input
				
				usr_input = input("\nNow enter book author with correct caps (if author not listed, press enter): ")
				
				if usr_input == "":
					book_author = "NIL"
				else:
					book_author = usr_input
					
				cur.execute("INSERT INTO books values(?, ?, ?);", ('NIL', book_title, book_author))
				con.commit()
				#print(book
				print(book_title, ",", book_author)
			elif usr_input.lower() == "search":
				usr_input = input("Do you want to search by isbn, book title, or book author?: ")
				
				if usr_input.lower() == "isbn":
					usr_input = input("\nisbn: ")
					res = cur.execute("SELECT * FROM books WHERE isbn = ?;", (usr_input,))
					rows = res.fetchall()
					
					search_count = 0
					for row in rows:
						search_count += 1
						print(row)
						
					if search_count == 0:
						print("\nNo search results found.\n")
				if usr_input.lower() == "book title" or usr_input.lower() == "title":
					usr_input = input("\nbook title: ")
					res = cur.execute("SELECT * FROM books WHERE title LIKE ?;", (f'%{usr_input}%',))
					rows = res.fetchall()
					
					search_count = 0
					for row in rows:
						search_count += 1
						print(row)
						
					if search_count == 0:
						print("\nNo search results found.\n")
				if usr_input.lower() == "author" or usr_input.lower() == "book author":
					usr_input = input("\nbook author: ")
					res = cur.execute("SELECT * FROM books WHERE author LIKE ?;", (f'%{usr_input}%',))
					rows = res.fetchall()
					
					search_count = 0
					for row in rows:
						search_count += 1
						print(row)
						
					if search_count == 0:
						print("\nNo search results found.\n")
			elif usr_input.lower() == "printall":
				res = cur.execute("SELECT * FROM books;")
				rows = res.fetchall()
				
				search_count = 0
				for row in rows:
					search_count += 1
					print(row)
				if search_count == 0:
					print("\nNo search results found.\n")
			elif usr_input.lower() == "countall":
				res = cur.execute("SELECT * FROM books;")
				rows = res.fetchall()
				book_num = 0
				
				for row in rows:
					book_num += 1
				print("\nNumber of books scanned:\n\n",book_num)
			elif usr_input.lower() == "exit":
				break	
			else:
				print("ERROR: Invalid Command. Please try again.")
		except Exception as e:
			print(f"ERROR: {e}\nPlease consult your favorite child.")
	
if __name__ == "__main__":
	with closing(sqlite3.connect(SCRIPT_DIR / "isbn.db")) as con:
		con.execute("CREATE TABLE IF NOT EXISTS books (isbn TEXT, title TEXT, author TEXT);")
		main(con)
