from flask import Flask, render_template, request, redirect, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = "dev"  # 用於 flash 訊息，正式環境請改強一點

# === MySQL 連線設定（依你的 Workbench 設定修改）===
app.config['MYSQL_HOST'] = '127.0.0.1'    # ✅ 主機 (localhost)
app.config['MYSQL_PORT'] = 3306     # 或 localhost
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "Phoebe07lu241011"
app.config["MYSQL_DB"] = "flask_test"      # 先在 Workbench 建好（見下方SQL）
app.config["MYSQL_CURSORCLASS"] = "DictCursor"  # 拿到 dict 方便模板使用
app.config["MYSQL_USE_UNICODE"] = True

mysql = MySQL(app)

# === 首頁：顯示表單 + 列表 ===
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        gender = request.form.get("gender")

        if not name or not email:
            flash("請填寫姓名與 Email")
            return redirect("/")

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users (name, gender, email) VALUES (%s, %s, %s)",
                (name,gender, email),
            )
            mysql.connection.commit()
            flash("新增成功！")
        except Exception as e:
            mysql.connection.rollback()
            flash(f"寫入失敗：{e}")
        finally:
            cur.close()

        return redirect("/")

    # GET：查詢列表
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, gender,email FROM users ORDER BY id DESC")
    users = cur.fetchall()
    cur.close()

    return render_template("index.html", users=users)

# === 刪除一筆 ===
@app.route("/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        mysql.connection.commit()
        flash("刪除成功！")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"刪除失敗：{e}")
    finally:
        cur.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
