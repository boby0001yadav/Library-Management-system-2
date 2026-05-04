from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------- DB ----------
def connect():
    return sqlite3.connect("database.db")

def init_db():
    conn = connect()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS books(
        id INTEGER PRIMARY KEY,
        title TEXT,
        author TEXT,
        available INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS issued(
        id INTEGER PRIMARY KEY,
        book_id INTEGER,
        issue_date TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS fines(
        id INTEGER PRIMARY KEY,
        amount INTEGER
    )""")

    # Create default users if not exist
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                  ("admin", generate_password_hash("admin"), "admin"))

    c.execute("SELECT * FROM users WHERE username='user'")
    if not c.fetchone():
        c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                  ("user", generate_password_hash("user"), "member"))

    conn.commit()
    conn.close()

init_db()

# ---------- LOGIN ----------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        conn = connect()
        c = conn.cursor()

        user = c.execute("SELECT * FROM users WHERE username=?",
                         (request.form["username"],)).fetchone()
        conn.close()

        if user and check_password_hash(user[2], request.form["password"]):
            session["role"] = user[3]
            return redirect("/admin" if user[3]=="admin" else "/member")

    return render_template("login.html")

# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    conn = connect()
    c = conn.cursor()

    books = c.execute("SELECT * FROM books").fetchall()
    issued = c.execute("SELECT * FROM issued").fetchall()
    total_fine = c.execute("SELECT SUM(amount) FROM fines").fetchone()[0] or 0

    stats = {
        "total": len(books),
        "issued": len(issued),
        "available": len([b for b in books if b[3]==1]),
        "fine": total_fine
    }

    conn.close()
    return render_template("admin.html", books=books, issued=issued, stats=stats)

# ---------- MEMBER ----------
@app.route("/member")
def member():
    if session.get("role") != "member":
        return redirect("/")

    conn = connect()
    c = conn.cursor()

    books = c.execute("SELECT * FROM books").fetchall()
    conn.close()

    return render_template("member.html", books=books)

# ---------- ADD BOOK ----------
@app.route("/add", methods=["POST"])
def add():
    conn = connect()
    c = conn.cursor()

    c.execute("INSERT INTO books(title,author,available) VALUES(?,?,1)",
              (request.form["title"], request.form["author"]))

    conn.commit()
    conn.close()
    return redirect("/admin")

# ---------- ISSUE ----------
@app.route("/issue/<int:id>")
def issue(id):
    conn = connect()
    c = conn.cursor()

    c.execute("UPDATE books SET available=0 WHERE id=?", (id,))
    c.execute("INSERT INTO issued(book_id,issue_date) VALUES(?,?)",
              (id, str(datetime.now().date())))

    conn.commit()
    conn.close()
    return redirect("/admin")

# ---------- RETURN ----------
@app.route("/return/<int:id>")
def return_book(id):
    conn = connect()
    c = conn.cursor()

    data = c.execute("SELECT * FROM issued WHERE id=?", (id,)).fetchone()

    issue_date = datetime.strptime(data[2], "%Y-%m-%d")
    days = (datetime.now() - issue_date).days

    fine = (days - 7) * 5 if days > 7 else 0

    c.execute("INSERT INTO fines(amount) VALUES(?)", (fine,))
    c.execute("DELETE FROM issued WHERE id=?", (id,))
    c.execute("UPDATE books SET available=1 WHERE id=?", (data[1],))

    conn.commit()
    conn.close()
    return redirect("/admin")

# ---------- SEARCH ----------
@app.route("/search", methods=["POST"])
def search():
    query = request.form["query"]

    conn = connect()
    c = conn.cursor()

    books = c.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ?",
                      ('%'+query+'%', '%'+query+'%')).fetchall()

    conn.close()
    return render_template("admin.html", books=books, issued=[], stats={"total":0,"issued":0,"available":0,"fine":0})

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(host="0.0.0.0", port=3000)
