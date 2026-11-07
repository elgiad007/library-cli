# These standard-library tools let us test interactive code automatically:
# io captures text, unittest supplies assertions, and patch replaces inputs.
import io
import sqlite3
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import library


class LibraryInteractionTests(unittest.TestCase):
	"""Group checks for the command-line interactions and stored book data."""
	# Inheriting TestCase gives this class assertion methods and test discovery.
	def setUp(self):
		# unittest calls setUp before each test. :memory: creates a fresh,
		# temporary database, so tests never modify the user's isbn.db file.
		# self keeps this connection available to the other instance methods.
		self.con = sqlite3.connect(":memory:")
		self.con.execute("CREATE TABLE books (isbn TEXT, title TEXT, author TEXT)")

	def tearDown(self):
		# Called after each test, even if an assertion fails, to release resources.
		self.con.close()

	def run_inputs(self, function, values, *args):
		"""Run a function with scripted answers and return its printed output."""
		# Functions can be passed as values. *args collects any extra positional
		# arguments into a tuple, then unpacks them when calling the function.
		output = io.StringIO()
		# Each input() gets the next value from side_effect. redirect_stdout
		# sends print output to an in-memory text buffer. Both with contexts
		# restore normal behavior when the block ends, even if the code raises.
		with patch("builtins.input", side_effect=values), redirect_stdout(output):
			function(self.con, *args)
		return output.getvalue()

	def test_manual_duplicate_requires_explicit_choice(self):
		"""Declining a duplicate leaves only the original book in the database."""
		# Arrange a saved book, act by trying to add it again, then assert both
		# the visible warning and the database result. Case differences match.
		self.run_inputs(library.add_book, ["Dune", "Frank Herbert"])
		output = self.run_inputs(library.add_book, ["dune", "frank herbert", "n"])
		self.assertIn("Already in library: Dune — Frank Herbert", output)
		self.assertEqual(self.con.execute("SELECT COUNT(*) FROM books").fetchone()[0], 1)

	def test_search_and_aliases(self):
		"""Search and legacy command names display the saved book correctly."""
		# Script a whole prompt session, ending with exit so the loop finishes.
		self.con.execute("INSERT INTO books VALUES (?, ?, ?)", ("9780441172719", "Dune", "Frank Herbert"))
		output = self.run_inputs(library.main, ["  SEARCH   herbert  ", "printall", "countall", "exit"])
		self.assertIn("Dune — Frank Herbert", output)
		self.assertIn("ISBN: 9780441172719", output)
		self.assertIn("1 book found.", output)
		self.assertIn("1 book.", output)

	def test_scan_fallback_keeps_isbn(self):
		"""Manual entry after a failed lookup retains the scanned ISBN."""
		# Replace the network lookup temporarily with a predictable None result:
		# this checks the no-details path without relying on internet access.
		with patch.object(library, "lookup_book", return_value=None):
			output = self.run_inputs(library.scan, ["9780441172719", "y", "Dune", "", "back"])
		self.assertIn("Added: Dune — Unknown author", output)
		self.assertEqual(self.con.execute("SELECT isbn FROM books").fetchone()[0], "9780441172719")


if __name__ == "__main__":
	# Discover and run methods whose names start with test_, reporting failures.
	unittest.main()
