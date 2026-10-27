import sqlite3

def init_db():
    conn = sqlite3.connect("library.db")
    cursor = conn.cursor()

    # Books table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        book_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT,
        quantity INTEGER 
    )
    """)

    # Members table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT
    )
    """)

    # Issued books table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issued_books (
        issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER,
        member_id INTEGER,
        issue_date DATE,
        return_date DATE,
        FOREIGN KEY(book_id) REFERENCES books(book_id),
        FOREIGN KEY(member_id) REFERENCES members(member_id)
    )
    """)

    conn.commit()
    conn.close()

def migrate_db():
    """Bug 6 Fix: migration moved into a function so it only runs explicitly,
    not on every import of database.py."""
    conn = sqlite3.connect("library.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE issued_books
            ADD COLUMN due_date TEXT
        """)
        print("Due date column added successfully.")
    except sqlite3.OperationalError:
        print("Due date column already exists.")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    migrate_db()
    print("Database created successfully!")