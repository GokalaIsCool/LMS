"""
One-shot script to apply all 13 bug fixes to app.py and database.py.
Run once, then delete this file.
"""
import os, re

BASE = os.path.dirname(__file__)
APP  = os.path.join(BASE, "app.py")
DB   = os.path.join(BASE, "database.py")

# ── helpers ──────────────────────────────────────────────────────────────────
def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save(path, content):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

def patch(src, old, new, label):
    # normalise to \n for matching, then put back original line endings
    lf   = src.replace("\r\n", "\n")
    old_ = old.replace("\r\n", "\n")
    new_ = new.replace("\r\n", "\n")
    if old_ not in lf:
        print(f"  MISS  - {label}")
        return src
    result = lf.replace(old_, new_, 1)
    print(f"  OK    - {label}")
    # restore CRLF if the original file had it
    if "\r\n" in src:
        result = result.replace("\n", "\r\n")
    return result


# ════════════════════════════════════════════════════════════════════════════
#  app.py  fixes
# ════════════════════════════════════════════════════════════════════════════
src = load(APP)

# ── Bug 1 + Bug 12 (add os import, env-based secret, abs DB path helper) ──
src = patch(src,
    old='''\
from flask import Flask, redirect, render_template, request, flash
import sqlite3
import csv
from flask import Response

app = Flask(__name__)
app.secret_key = "library_management_system"''',
    new='''\
from flask import Flask, redirect, render_template, request, flash
import sqlite3
import csv
import os
from flask import Response

app = Flask(__name__)
# Bug 1 Fix: secret key from env-var, not hardcoded in source
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# Bug 12 Fix: absolute DB path so the app works regardless of cwd
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.db")


def get_db():
    """Return a new SQLite connection using the absolute DB path."""
    return sqlite3.connect(DB_PATH)''',
    label="Bug 1 – hardcoded secret key | Bug 12 – relative DB path")

# ── Bug 12: replace every sqlite3.connect("library.db") with get_db() ──────
src = src.replace('sqlite3.connect("library.db")', "get_db()")
print("  OK    - Bug 12 - all connect() calls patched to get_db()")

# ── Bug 2a: int(quantity) crash in books() POST ──────────────────────────────
src = patch(src,
    old='''\
        if int(quantity) <= 0:
            flash(
                "Quantity must be greater than zero.",
                "error"
            )
        else:''',
    new='''\
        try:
            qty_int = int(quantity)
        except ValueError:
            flash("Quantity must be a valid number.", "error")
            conn.close()
            return redirect("/books")
        # Bug 2a Fix: guard against non-numeric input before int() cast
        if qty_int <= 0:
            flash(
                "Quantity must be greater than zero.",
                "error"
            )
        else:''',
    label="Bug 2a – int(quantity) ValueError crash in books()")

# ── Bug 2b: int(quantity) crash in edit_book() POST ─────────────────────────
src = patch(src,
    old='''\
        if int(quantity) < 0:
            flash(
                "Quantity cannot be negative.",
                "error")
            conn.close()
            return redirect(f"/edit-book/{book_id}")''',
    new='''\
        try:
            qty_int = int(quantity)
        except ValueError:
            flash("Quantity must be a valid number.", "error")
            conn.close()
            return redirect(f"/edit-book/{book_id}")
        # Bug 2b Fix: guard against non-numeric input before int() cast
        if qty_int < 0:
            flash(
                "Quantity cannot be negative.",
                "error")
            conn.close()
            return redirect(f"/edit-book/{book_id}")''',
    label="Bug 2b – int(quantity) ValueError crash in edit_book()")

# also replace the bare quantity with qty_int in edit_book UPDATE
src = patch(src,
    old='''\
        cursor.execute("""
            UPDATE books
            SET
                title=?,
                author=?,
                category=?,
                quantity=?
            WHERE book_id=?
        """, (title, author, category, quantity, book_id))''',
    new='''\
        cursor.execute("""
            UPDATE books
            SET
                title=?,
                author=?,
                category=?,
                quantity=?
            WHERE book_id=?
        """, (title, author, category, qty_int, book_id))''',
    label="Bug 2b – use validated qty_int in UPDATE")

# also replace quantity in INSERT (books POST) with qty_int
src = patch(src,
    old='''\
            cursor.execute("""
                INSERT INTO books(title,author,category,quantity)
                VALUES(?,?,?,?)
            """,(title,author,category,quantity))''',
    new='''\
            cursor.execute("""
                INSERT INTO books(title,author,category,quantity)
                VALUES(?,?,?,?)
            """,(title,author,category,qty_int))''',
    label="Bug 2a – use validated qty_int in INSERT")

# ── Bug 3: NoneType crash in issue_book() ────────────────────────────────────
src = patch(src,
    old='''\
        quantity = cursor.fetchone()[0]

        if quantity <= 0:

            flash(
                "No copies available.",
                "error"
            )

            conn.close()

            return redirect("/issue-book")''',
    new='''\
        # Bug 3 Fix: guard against book_id not found in DB
        row = cursor.fetchone()
        if row is None:
            flash("Book not found.", "error")
            conn.close()
            return redirect("/issue-book")
        quantity = row[0]

        if quantity <= 0:

            flash(
                "No copies available.",
                "error"
            )

            conn.close()

            return redirect("/issue-book")''',
    label="Bug 3 – NoneType crash when book_id missing in issue_book()")

# ── Bug 4 + Bug 5: double-return & NoneType crash in return_book() ───────────
src = patch(src,
    old='''\
    if request.method == "POST":

        issue_id = request.form["issue_id"]

        cursor.execute("""
            SELECT book_id
            FROM issued_books
            WHERE issue_id=?
        """, (issue_id,))

        book_id = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE issued_books
            SET return_date = DATE('now')
            WHERE issue_id=?
        """, (issue_id,))

        cursor.execute("""
            UPDATE books
            SET quantity = quantity + 1
            WHERE book_id=?
        """, (book_id,))

        conn.commit()''',
    new='''\
    if request.method == "POST":

        issue_id = request.form["issue_id"]

        # Bug 4 + 5 Fix: fetch only un-returned records to prevent double-return
        # and guard against None if issue_id is invalid / already returned
        cursor.execute("""
            SELECT book_id
            FROM issued_books
            WHERE issue_id=? AND return_date IS NULL
        """, (issue_id,))

        row = cursor.fetchone()
        if row is None:
            flash("Invalid issue record or book already returned.", "error")
            conn.close()
            return redirect("/return-book")

        book_id = row[0]

        cursor.execute("""
            UPDATE issued_books
            SET return_date = DATE('now')
            WHERE issue_id=?
        """, (issue_id,))

        cursor.execute("""
            UPDATE books
            SET quantity = quantity + 1
            WHERE book_id=?
        """, (book_id,))

        conn.commit()
        flash("Book returned successfully!", "success")''',
    label="Bug 4+5 – NoneType crash + double-return in return_book()")

# ── Bug 7: double conn.commit() in edit_book() ───────────────────────────────
src = patch(src,
    old='''\
        conn.commit()
        flash(
            "Book updated successfully!",
            "success")

        conn.commit()
        conn.close()''',
    new='''\
        conn.commit()
        flash(
            "Book updated successfully!",
            "success")
        # Bug 7 Fix: removed duplicate conn.commit()
        conn.close()''',
    label="Bug 7 – duplicate conn.commit() in edit_book()")

# ── Bug 10: missing phone validation in edit_member() ────────────────────────
src = patch(src,
    old='''\
        cursor.execute("""SELECT * FROM members WHERE email = ? AND member_id != ? """, (email, member_id))''',
    new='''\
        # Bug 10 Fix: validate phone on edit, same rule as on add
        if not phone.isdigit() or len(phone) != 10:
            flash("Phone number must contain exactly 10 digits.", "error")
            conn.close()
            return redirect(f"/edit-member/{member_id}")

        cursor.execute("""SELECT * FROM members WHERE email = ? AND member_id != ? """, (email, member_id))''',
    label="Bug 10 – missing phone validation in edit_member()")

# ── Bug 11: CSV export doesn't escape commas ─────────────────────────────────
src = patch(src,
    old='''\
    def generate():

        yield "ID,Title,Author,Category,Quantity\\n"

        for book in books:

            yield f"{book[0]},{book[1]},{book[2]},{book[3]},{book[4]}\\n"

    return Response(

        generate(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
            "attachment; filename=books.csv"

        }

    )''',
    new='''\
    def generate():
        import io
        # Bug 11 Fix: use csv.writer to properly escape commas/quotes in data
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "Title", "Author", "Category", "Quantity"])
        yield buf.getvalue()
        for book in books:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(book)
            yield buf.getvalue()

    return Response(

        generate(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
            "attachment; filename=books.csv"

        }

    )''',
    label="Bug 11 – CSV export missing comma escaping")

save(APP, src)
print()
print("app.py – all fixes applied.")

# ════════════════════════════════════════════════════════════════════════════
#  database.py  fix  (Bug 6 – module-level migration runs on import)
# ════════════════════════════════════════════════════════════════════════════
src = load(DB)
src = patch(src,
    old='''\
if __name__ == "__main__":
    init_db()
    print("Database created successfully!")


import sqlite3

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
conn.close()''',
    new='''\
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
    print("Database created successfully!")''',
    label="Bug 6 – module-level migration code in database.py")

save(DB, src)
print()
print("database.py – all fixes applied.")
print()
print("All done! You can now delete apply_fixes.py.")
