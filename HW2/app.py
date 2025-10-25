from flask import Flask, render_template, request, redirect, url_for, flash, session, g

# 讓 flask_mysqldb 使用 PyMySQL
import pymysql
pymysql.install_as_MySQLdb()
from flask_mysqldb import MySQL

from functools import wraps
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")

# === MySQL 連線設定（讀 .env） ===
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

# ---------------- 共用 SQL 小工具 ----------------
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

# 依分類名稱取得 id（沒有就回 None）
def get_category_id_by_name(name: str):
    if not name:
        return None
    row = query_one("SELECT id FROM categories WHERE name=%s", [name])
    return row["id"] if row else None

# ---------------- 登入保護 ----------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("請先登入")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = query_one("SELECT id, username FROM users WHERE id=%s", [uid])

# ===================== 使用者：註冊 / 登入 / 登出 =====================
# 說明：按你的要求，這裡密碼改為「明文」存放 users.password
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
        exec_sql("INSERT INTO users (username, password) VALUES (%s, %s)", [username, password])
        flash("註冊成功，請登入")
        return redirect(url_for("login"))
    return render_template("login.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_one("SELECT id, username, password FROM users WHERE username=%s", [username])
        if not user or user["password"] != password:
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
# 說明：
# - 資料表改用 tasks（不再是 todos）
# - 顯示列表時以 JOIN 把分類名稱帶出（categories.name AS category_name）
# - 僅回傳目前登入者自己的資料（WHERE t.user_id = g.user["id"]）
@app.route("/")
@login_required
def index():
    # 允許以 ?category=school/work/other 篩選
    category_name = request.args.get("category")
    params = [g.user["id"]]

    base_sql = (
        "SELECT "
        "  t.id, t.task, t.status, t.note, "
        "  COALESCE(c.name, 'uncategorized') AS category_name, "
        "  t.updated_at "
        "FROM tasks AS t "
        "INNER JOIN users AS u ON u.id = t.user_id "        # 作業要求：示範 JOIN
        "LEFT JOIN categories AS c ON c.id = t.category_id " # LEFT JOIN：即使沒分類也顯示
        "WHERE t.user_id = %s "
    )

    if category_name:
        base_sql += "AND c.name = %s "
        params.append(category_name)

    base_sql += "ORDER BY t.id DESC"

    todos = query_all(base_sql, params)

    # 供頁面選單使用
    cats = query_all("SELECT id, name FROM categories ORDER BY id")
    return render_template("index.html", todos=todos, categories=cats, category=category_name)

@app.route("/add", methods=["POST"])
@login_required
def add():
    task = request.form.get("task", "").strip()
    category_name = request.form.get("category", "").strip() or None  # 'school' / 'work' / 'other' / ''
    status = "未完成"
    note = ""
    if not task:
        flash("請輸入任務內容")
        return redirect(url_for("index"))

    cat_id = get_category_id_by_name(category_name)
    exec_sql(
        "INSERT INTO tasks (task, status, note, user_id, category_id) VALUES (%s, %s, %s, %s, %s)",
        (task, status, note, g.user["id"], cat_id)
    )
    return redirect(url_for("index", category=category_name) if category_name else url_for("index"))

@app.route("/complete/<int:task_id>")
@login_required
def complete(task_id):
    # 僅能操作自己的任務
    exec_sql("UPDATE tasks SET status='完成' WHERE id=%s AND user_id=%s", (task_id, g.user["id"]))
    return redirect(url_for("index"))

@app.route("/delete/<int:task_id>")
@login_required
def delete(task_id):
    exec_sql("DELETE FROM tasks WHERE id=%s AND user_id=%s", (task_id, g.user["id"]))
    return redirect(url_for("index"))

# 編輯頁：GET 顯示、POST 儲存
@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit(task_id):
    if request.method == "POST":
        task = request.form.get("task", "").strip()
        category_name = request.form.get("category", "").strip()
        status = request.form.get("status", "未完成").strip()
        note = request.form.get("note", "").strip()
        cat_id = get_category_id_by_name(category_name)

        exec_sql(
            "UPDATE tasks SET task=%s, status=%s, note=%s, category_id=%s "
            "WHERE id=%s AND user_id=%s",
            (task, status, note, cat_id, task_id, g.user["id"])
        )
        flash("已更新任務")
        return redirect(url_for("index", category=category_name) if category_name else url_for("index"))

    # GET：抓資料（含分類名，方便畫面顯示）
    row = query_one(
        "SELECT t.id, t.task, t.status, t.note, COALESCE(c.name,'') AS category_name "
        "FROM tasks t "
        "LEFT JOIN categories c ON c.id=t.category_id "
        "WHERE t.id=%s AND t.user_id=%s",
        (task_id, g.user["id"])
    )
    if not row:
        flash("找不到任務")
        return redirect(url_for("index"))

    cats = query_all("SELECT id, name FROM categories ORDER BY id")
    return render_template("edit.html", todo=row, categories=cats)

# 只改備註（列表頁快速更新）
@app.route("/update_note/<int:task_id>", methods=["POST"])
@login_required
def update_note(task_id):
    note = request.form.get("note", "").strip()
    exec_sql("UPDATE tasks SET note=%s WHERE id=%s AND user_id=%s", (note, task_id, g.user["id"]))
    flash("備註已更新")
    category_name = request.args.get("category")
    return redirect(url_for("index", category=category_name) if category_name else url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
