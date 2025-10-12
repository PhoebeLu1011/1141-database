from flask import Flask, render_template, request, redirect, url_for, flash, session, g

# 先安裝 PyMySQL 當 MySQLdb 的替身
import pymysql
pymysql.install_as_MySQLdb()

# 再匯入 flask_mysqldb（此時它會拿到 PyMySQL）
from flask_mysqldb import MySQL


# 密碼雜湊
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


import os
from dotenv import load_dotenv
load_dotenv()  # 讀取 .env（若沒裝 python-dotenv 也不會壞）


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")  # 沒設就用開發預設

# === MySQL 連線設定（讀 env） ===
app.config.update(
    MYSQL_HOST=os.getenv("MYSQL_HOST", "127.0.0.1"),
    MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
    MYSQL_USER=os.getenv("MYSQL_USER", "root"),
    MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),
    MYSQL_DB=os.getenv("MYSQL_DB", "todolist"),
    MYSQL_CURSORCLASS=os.getenv("MYSQL_CURSORCLASS", "DictCursor"),
    MYSQL_CHARSET=os.getenv("MYSQL_CHARSET", "utf8mb4"),
)

mysql = MySQL(app)

# ---- 小工具：執行 SQL ----
def query_all(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows

def query_one(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    row = cur.fetchone()
    cur.close()
    return row

def exec_sql(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    mysql.connection.commit()
    cur.close()

# ---- 登入保護裝飾器 ----
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("請先登入")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

# ---- 每次請求載入目前使用者 ----
@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = query_one("SELECT id, username FROM users WHERE id=%s", [uid])

# ===================== 使用者：註冊 / 登入 / 登出 =====================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("請填寫帳號與密碼")
            return redirect(url_for("register"))
        exists = query_one("SELECT id FROM users WHERE username=%s", [username])
        if exists:
            flash("帳號已被使用")
            return redirect(url_for("register"))
        pw_hash = generate_password_hash(password)
        exec_sql("INSERT INTO users (username, password_hash) VALUES (%s, %s)", [username, pw_hash])
        flash("註冊成功，請登入")
        return redirect(url_for("login"))
    return render_template("login.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_one("SELECT id, username, password_hash FROM users WHERE username=%s", [username])
        if not user or not check_password_hash(user["password_hash"], password):
            flash("帳號或密碼錯誤")
            return redirect(url_for("login"))
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash("登入成功")
        nxt = request.args.get("next")
        return redirect(nxt or url_for("index"))
    return render_template("login.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("您已登出")
    return redirect(url_for("login"))

# ===================== 待辦：列表 / 新增 / 編輯 / 完成 / 刪除 =====================
@app.route("/")
@login_required
def index():
    category = request.args.get("category")  # None / work / school / other
    if category:
        todos = query_all(
            "SELECT id, task, category, status, note FROM todos "
            "WHERE user_id=%s AND category=%s ORDER BY id DESC",
            [g.user["id"], category]
        )
    else:
        todos = query_all(
            "SELECT id, task, category, status, note FROM todos "
            "WHERE user_id=%s ORDER BY id DESC",
            [g.user["id"]]
        )
    return render_template("index.html", todos=todos, category=category)




@app.route("/add", methods=["POST"])
@login_required
def add():
    task = request.form.get("task", "").strip()
    category = request.form.get("category", "").strip() or "other"
    if not task:
        flash("請輸入任務內容")
        return redirect(url_for("index"))
    exec_sql(
        "INSERT INTO todos (task, category, status, user_id) VALUES (%s, %s, %s, %s)",
        (task, category, "未完成", g.user["id"])
    )
    return redirect(url_for("index"))

@app.route("/complete/<int:todo_id>")
@login_required
def complete(todo_id):
    exec_sql("UPDATE todos SET status='完成' WHERE id=%s", (todo_id,))
    return redirect(url_for("index"))

@app.route("/delete/<int:todo_id>")
@login_required
def delete(todo_id):
    exec_sql("DELETE FROM todos WHERE id=%s", (todo_id,))
    return redirect(url_for("index"))

# ====== 編輯頁（GET 顯示表單；POST 送出更新）======
@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    if request.method == "POST":
        task = request.form.get("task", "").strip()
        category = request.form.get("category", "").strip()
        status = request.form.get("status", "未完成").strip()
        note = request.form.get("note", "").strip()
        exec_sql(
            "UPDATE todos SET task=%s, category=%s, status=%s, note=%s WHERE id=%s",
            (task, category, status, note, todo_id)
        )
        flash("已更新任務")
        return redirect(url_for("index"))

    # GET：抓資料並顯示編輯頁
    rows = query_all("SELECT id, task, category, status, note FROM todos WHERE id=%s", (todo_id,))
    if not rows:
        flash("找不到任務")
        return redirect(url_for("index"))
    todo = rows[0]
    return render_template("edit.html", todo=todo)

# ====== 在列表頁快速更新備註（只改 note）======
@app.route("/update_note/<int:todo_id>", methods=["POST"])
@login_required
def update_note(todo_id):
    note = request.form.get("note", "").strip()
    exec_sql("UPDATE todos SET note=%s WHERE id=%s", (note, todo_id))
    flash("備註已更新")
    # 回到當前分類（如果有）
    category = request.args.get("category")
    return redirect(url_for("index", category=category) if category else url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
