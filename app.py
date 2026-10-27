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
    return sqlite3.connect(DB_PATH)

@app.route("/")
def home():

    conn = get_db()
    cursor = conn.cursor()

    # Total books
    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]

    # Total members
    cursor.execute("SELECT COUNT(*) FROM members")
    total_members = cursor.fetchone()[0]

    # Currently issued books
    cursor.execute("""
        SELECT COUNT(*)
        FROM issued_books
        WHERE return_date IS NULL
    """)
    books_issued = cursor.fetchone()[0]

    # Overdue books
    cursor.execute("""
        SELECT COUNT(*)
        FROM issued_books
        WHERE
            return_date IS NULL
            AND due_date < DATE('now')
    """)
    overdue_books = cursor.fetchone()[0]

    # Low stock books
    cursor.execute("""
        SELECT COUNT(*)
        FROM books
        WHERE quantity <= 2
    """)
    low_stock = cursor.fetchone()[0]

    # Available copies
    cursor.execute("""
        SELECT SUM(quantity)
        FROM books
    """)
    available_books = cursor.fetchone()[0]

    if available_books is None:
        available_books = 0

    # Recently added books
    cursor.execute("""
        SELECT title
        FROM books
        ORDER BY book_id DESC
        LIMIT 5
    """)

    recent_books = cursor.fetchall()

    conn.close()

    return render_template(
        "index.html",
        total_books=total_books,
        total_members=total_members,
        books_issued=books_issued,
        overdue_books=overdue_books,
        low_stock=low_stock,
        available_books=available_books,
        recent_books=recent_books
    )


@app.route("/books", methods=["GET", "POST"])
def books():

    conn = get_db()
    cursor = conn.cursor()

    # Add Book
    if request.method == "POST":

        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        quantity = request.form["quantity"]

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
        else:
            cursor.execute("""
                           SELECT * FROM books WHERE title=? AND author=? """, (title, author))
            existing = cursor.fetchone()
            if existing:
                flash(
                    "Book already exists.",
                    "error"
                )

                conn.close()
                return redirect("/books")

            cursor.execute("""
                INSERT INTO books(title,author,category,quantity)
                VALUES(?,?,?,?)
            """,(title,author,category,qty_int))

            conn.commit()

            flash(
                "Book added successfully!",
                "success"
            )



    # Search
    search = request.args.get("search")

    if search:

        cursor.execute("""
            SELECT *
            FROM books
            WHERE
                title LIKE ?
                OR author LIKE ?
                OR category LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))

    else:

        cursor.execute("SELECT * FROM books")

    books = cursor.fetchall()

    conn.close()

    return render_template(
        "books.html",
        books=books,
        search=search
    )

@app.route("/delete-book/<int:book_id>")
def delete_book(book_id):

    conn = get_db()
    cursor = conn.cursor()

    # Check if the book is currently issued
    cursor.execute("""
        SELECT *
        FROM issued_books
        WHERE
            book_id = ?
            AND return_date IS NULL
    """, (book_id,))

    active_issue = cursor.fetchone()

    if active_issue:

        flash(
            "Cannot delete a book that is currently issued.",
            "error"
        )

        conn.close()

        return redirect("/books")

    cursor.execute(
        "DELETE FROM books WHERE book_id=?",
        (book_id,)
    )

    conn.commit()

    flash(
        "Book deleted successfully!",
        "success"
    )

    conn.close()

    return redirect("/books")

@app.route("/edit-book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        quantity = request.form["quantity"]

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
            return redirect(f"/edit-book/{book_id}")
        
        
        cursor.execute("""
            UPDATE books
            SET
                title=?,
                author=?,
                category=?,
                quantity=?
            WHERE book_id=?
        """, (title, author, category, qty_int, book_id))

        conn.commit()
        flash(
            "Book updated successfully!",
            "success")
        # Bug 7 Fix: removed duplicate conn.commit()
        conn.close()

        return redirect("/books")

    cursor.execute(
        "SELECT * FROM books WHERE book_id=?",
        (book_id,)
    )

    book = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_book.html",
        book=book
    )



@app.route("/members", methods=["GET", "POST"])
def members():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]

        if not phone.isdigit() or len(phone) != 10:
            flash(
                "Phone number must contain exactly 10 digits.",
                "error")
            conn.close()
            return redirect("/members")

        # Check duplicate email
        cursor.execute(
            "SELECT * FROM members WHERE email=?",
            (email,)
        )

        existing_member = cursor.fetchone()

        if existing_member:

            flash(
                "A member with this email already exists.",
                "error"
            )

        else:

            cursor.execute("""
                INSERT INTO members(name,email,phone)
                VALUES(?,?,?)
            """, (name, email, phone))

            conn.commit()

            flash(
                "Member added successfully!",
                "success"
            )

    search = request.args.get("search")

    if search:

        cursor.execute("""
            SELECT *
            FROM members
            WHERE
            name LIKE ?
            OR email LIKE ?
            OR phone LIKE ?
        """,
        (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

    else:

        cursor.execute(
            "SELECT * FROM members"
        )

    members = cursor.fetchall()

    conn.close()

    return render_template(
        "members.html",
        members=members,
        search=search
    )

@app.route("/edit-member/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]

        # Bug 10 Fix: validate phone on edit, same rule as on add
        if not phone.isdigit() or len(phone) != 10:
            flash("Phone number must contain exactly 10 digits.", "error")
            conn.close()
            return redirect(f"/edit-member/{member_id}")

        cursor.execute("""SELECT * FROM members WHERE email = ? AND member_id != ? """, (email, member_id))
        
        existing = cursor.fetchone()
        if existing:
            flash(
                "Email already exists.","error")
            conn.close()
            return redirect(f"/edit-member/{member_id}")
        
        
        cursor.execute("""
            UPDATE members
            SET
            name=?,
            email=?,
            phone=?
            WHERE member_id=?
        """,
        (
            name,
            email,
            phone,
            member_id
        ))

        conn.commit()

        flash(
            "Member updated successfully!",
            "success"
        )

        conn.close()

        return redirect("/members")

    cursor.execute(
        "SELECT * FROM members WHERE member_id=?",
        (member_id,)
    )

    member = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_member.html",
        member=member
    )

@app.route("/delete-member/<int:member_id>")
def delete_member(member_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM issued_books
        WHERE
            member_id = ?
            AND return_date IS NULL
    """, (member_id,))

    borrowed = cursor.fetchone()

    if borrowed:

        flash(
            "Member still has borrowed books.",
            "error"
        )

        conn.close()

        return redirect("/members")

    cursor.execute(
        "DELETE FROM members WHERE member_id=?",
        (member_id,)
    )

    conn.commit()

    flash(
        "Member deleted successfully!",
        "success"
    )

    conn.close()

    return redirect("/members")


@app.route("/issue-book", methods=["GET", "POST"])
def issue_book():

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        book_id = request.form["book_id"]
        member_id = request.form["member_id"]

        # Check if the member already has this book issued
        cursor.execute("""
            SELECT *
            FROM issued_books
            WHERE
                book_id = ?
                AND member_id = ?
                AND return_date IS NULL
        """, (book_id, member_id))

        already_issued = cursor.fetchone()

        if already_issued:

            flash(
                "This member already has this book issued.",
                "error"
            )

            conn.close()

            return redirect("/issue-book")

        # Check available quantity
        cursor.execute(
            "SELECT quantity FROM books WHERE book_id=?",
            (book_id,)
        )

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

            return redirect("/issue-book")

        # Issue the book
        cursor.execute("""
            INSERT INTO issued_books
            (
                book_id,
                member_id,
                issue_date,
                due_date
            )
            VALUES
            (
                ?,
                ?,
                DATE('now'),
                DATE('now', '+14 day')
            )
        """, (book_id, member_id))

        # Reduce available quantity
        cursor.execute("""
            UPDATE books
            SET quantity = quantity - 1
            WHERE book_id = ?
        """, (book_id,))

        conn.commit()

        flash(
            "Book issued successfully!",
            "success"
        )

        conn.close()

        return redirect("/issue-book")

    # Load available books
    cursor.execute("""
        SELECT book_id, title
        FROM books
        WHERE quantity > 0
    """)

    books = cursor.fetchall()

    # Load members
    cursor.execute("""
        SELECT member_id, name
        FROM members
    """)

    members = cursor.fetchall()

    conn.close()

    return render_template(
        "issue_book.html",
        books=books,
        members=members
    )

@app.route("/return-book", methods=["GET", "POST"])
def return_book():

    conn = get_db()
    cursor = conn.cursor()

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
        flash("Book returned successfully!", "success")

    cursor.execute("""
        SELECT
            issue_id,
            title,
            name
        FROM issued_books
        JOIN books
            ON books.book_id = issued_books.book_id
        JOIN members
            ON members.member_id = issued_books.member_id
        WHERE return_date IS NULL
    """)

    issued = cursor.fetchall()

    conn.close()

    return render_template(
        "return_book.html",
        issued=issued
    )

@app.route("/history")
def history():

    conn = get_db()
    cursor = conn.cursor()

    search = request.args.get("search", "")
    status = request.args.get("status", "")

    query = """
        SELECT
            ib.issue_id,
            b.title,
            m.name,
            ib.issue_date,
            ib.due_date,
            ib.return_date,

            CASE

                WHEN ib.return_date IS NOT NULL
                    THEN 'Returned'

                WHEN DATE('now') > ib.due_date
                    THEN 'Overdue'

                ELSE 'Issued'

            END AS status

        FROM issued_books ib

        JOIN books b
            ON ib.book_id=b.book_id

        JOIN members m
            ON ib.member_id=m.member_id

        WHERE
            (b.title LIKE ? OR m.name LIKE ?)
    """

    params = [
        f"%{search}%",
        f"%{search}%"
    ]

    if status != "":

        query += """

        AND

        CASE

            WHEN ib.return_date IS NOT NULL
                THEN 'Returned'

            WHEN DATE('now') > ib.due_date
                THEN 'Overdue'

            ELSE 'Issued'

        END = ?

        """

        params.append(status)

    query += """

    ORDER BY ib.issue_date DESC

    """

    cursor.execute(query, params)

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        history=history,
        search=search,
        status=status
    )


@app.route("/export/books")
def export_books():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM books
    """)

    books = cursor.fetchall()

    conn.close()

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

    )


if __name__ == "__main__":
    app.run(debug=True)