from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = "dev"  # TODO: 之後換強一點

# === MySQL 連線設定 ===
app.config["MYSQL_HOST"] = "127.0.0.1"
app.config["MYSQL_PORT"] = 3306
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "Phoebe07lu241011"          # ← 依實際密碼
app.config["MYSQL_DB"] = "todolist"         # ← 先建好 DB
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_CHARSET"] = "utf8mb4"

mysql = MySQL(app)

# ---- 小工具：執行 SQL ----
def query_all(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows

def exec_sql(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    mysql.connection.commit()
    cur.close()

# ---- 路由 ----
@app.route("/")
def index():
    category = request.args.get("category")  # None / work / school / other

    if category:
        todos = query_all("SELECT id, task, category, status FROM todos WHERE category=%s ORDER BY id DESC", [category])
    else:
        todos = query_all("SELECT id, task, category, status FROM todos ORDER BY id DESC")

    return render_template("index.html", todos=todos, category=category)

@app.route("/add", methods=["POST"])
def add():
    task = request.form.get("task", "").strip()
    category = request.form.get("category", "").strip()
    if not task:
        flash("請輸入任務內容")
        return redirect(url_for("index"))
    if not category:
        category = "other"
    exec_sql("INSERT INTO todos (task, category) VALUES (%s, %s)", (task, category))
    return redirect(url_for("index"))

@app.route("/complete/<int:todo_id>")
def complete(todo_id):
    exec_sql("UPDATE todos SET status='完成' WHERE id=%s", (todo_id,))
    return redirect(url_for("index"))

@app.route("/delete/<int:todo_id>")
def delete(todo_id):
    exec_sql("DELETE FROM todos WHERE id=%s", (todo_id,))
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
