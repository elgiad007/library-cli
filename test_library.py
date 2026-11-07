import io
import sqlite3
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import library


class LibraryInteractionTests(unittest.TestCase):
	def setUp(self):
		self.con = sqlite3.connect(":memory:")
		self.con.execute("CREATE TABLE books (isbn TEXT, title TEXT, author TEXT)")

	def tearDown(self):
		self.con.close()

	def run_inputs(self, function, values, *args):
		output = io.StringIO()
		with patch("builtins.input", side_effect=values), redirect_stdout(output):
			function(self.con, *args)
		return output.getvalue()

	def test_manual_duplicate_requires_explicit_choice(self):
		self.run_inputs(library.add_book, ["Dune", "Frank Herbert"])
		output = self.run_inputs(library.add_book, ["dune", "frank herbert", "n"])
		self.assertIn("Already in library: Dune — Frank Herbert", output)
		self.assertEqual(self.con.execute("SELECT COUNT(*) FROM books").fetchone()[0], 1)

	def test_search_and_aliases(self):
		self.con.execute("INSERT INTO books VALUES (?, ?, ?)", ("9780441172719", "Dune", "Frank Herbert"))
		output = self.run_inputs(library.main, ["  SEARCH   herbert  ", "printall", "countall", "exit"])
		self.assertIn("Dune — Frank Herbert", output)
		self.assertIn("ISBN: 9780441172719", output)
		self.assertIn("1 book found.", output)
		self.assertIn("1 book.", output)

	def test_scan_fallback_keeps_isbn(self):
		with patch.object(library, "lookup_book", return_value=None):
			output = self.run_inputs(library.scan, ["9780441172719", "y", "Dune", "", "back"])
		self.assertIn("Added: Dune — Unknown author", output)
		self.assertEqual(self.con.execute("SELECT isbn FROM books").fetchone()[0], "9780441172719")


if __name__ == "__main__":
	unittest.main()
