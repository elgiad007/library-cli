import os
import pygame
import sqlite3
import isbnlib

pygame.init()
pygame.mixer.init()

con = sqlite3.connect("isbn.db")
cur = con.cursor()

def scan(lib_error):
	while True:
		lib_error = False
		
		#scan_error = False
		#is_scan = True
		#os.system('clear')
		repeat = False
		
		usr_input = input("scan or exit: ")
		
		if usr_input.lower() == "exit":
			is_scan = False
			break
		
		res = cur.execute("SELECT isbn FROM books WHERE isbn = ?;", (usr_input,))
		copys = res.fetchall()
		
		for copy in copys:
			repeat = True
			print("\nBook already added.\n")
			alert = pygame.mixer.Sound("beeping_for_book_scanner.wav")
			alert.play()
			
		if repeat == True:
			continue
		if len(usr_input) == 13 or len(usr_input) == 10:
			book = isbnlib.meta(usr_input, service='openl')
			cur.execute("INSERT INTO books values(?, ?, ?);", (usr_input, book["Title"], book["Authors"][0]))
			con.commit()
			#print(book
			print(book["Title"], book["Authors"])
		else:
			print("ERROR: Invalid ISBN number. Please try again.")

def main():
	
	lib_error = False
	#scan_error = False
	#is_scan = False
	
	#cur.execute("drop table if exists books;")
	#cur.execute("CREATE TABLE books (isbn TEXT, title TEXT, author TEXT);")
	
	while True:
		print("\n______________________________\nCommands:\n\n'scan'\n'entermanually'\n'search'\n'printall'\n'countall'\n'exit'\n\n")
		
		usr_input = input("Type cmd: ")
		
		try:
			#if scan_error == True:
				#scan(scan_error=scan_error, is_scan=is_scan)
				
			if lib_error == True:
				scan(lib_error=lib_error)
			
			if usr_input.lower() == "scan":
				scan(lib_error=lib_error)
			elif usr_input.lower() == "entermanually":
				usr_input = input("Enter book title with correct caps: ")
				
				res = cur.execute("SELECT title FROM books WHERE title = ?;", (usr_input.lower(),))
				copys = res.fetchall()
				
				for copy in copys:
					print("\nBook already added.\n")
					alert = pygame.mixer.Sound("beeping_for_book_scanner.wav")
					alert.play()
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
			#if is_scan:
				#scan_error = True
				#is_scan = False
			if e == "Title":
				lib_error = True
			print(f"ERROR: {e}\nPlease consult your favorite child.")
	
if __name__ == "__main__":
	main()
