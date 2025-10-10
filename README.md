## HW1

In Homework 1, I built a simple Flask–MySQL **to-do list** application.
It demonstrates how to connect Flask to a MySQL database and use a frontend form to insert and display data.

### | 🎬 Demo Video:
- YouTube link:****

### | 🔗 Source Code:

### | 🖼️ Interface Preview:


### | 📁 Project Structure:
```
HW1/
├── app.py # MAIN
├── templates/ # HTML
│ ├── index.html 
│ ├── login.html 
│ └── edit.html 
└── .env
└── requirements.txt
```
### | 🔗 Important Code:
##### 1. Flask × MySQL Configuration
```py
import os
from flask import Flask
from dotenv import load_dotenv
import pymysql
pymysql.install_as_MySQLdb() 
# Use PyMySQL as a drop-in replacement for MySQLdb
from flask_mysqldb import MySQL

load_dotenv()
app = Flask(__name__)

# MySQL connection settings(.env)
app.config.update(
MYSQL_HOST=os.getenv("MYSQL_HOST", "127.0.0.1"),
MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
MYSQL_USER=os.getenv("MYSQL_USER", "root"),
MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),
MYSQL_DB=os.getenv("MYSQL_DB", "todolist"),
MYSQL_CURSORCLASS="DictCursor",
)
mysql = MySQL(app)
```
#### 2. Data Insertion 
This code snippet precisely demonstrates **how Flask handles POST requests, retrieves data from a form, and inserts it into the MySQL database.**
```py
# ---- 核心 SQL 執行函數 (簡潔展示) ----
def exec_sql(sql, params=None):
    cur = mysql.connection.cursor()
    cur.execute(sql, params or ())
    mysql.connection.commit()
    cur.close()

# ---- 待辦新增路由 (處理前端 POST) ----
@app.route("/add", methods=["POST"])
@login_required
def add():
    task = request.form.get("task", "").strip()
    category = request.form.get("category", "").strip() or "other"
    if not task:
        flash("請輸入任務內容")
        return redirect(url_for("index"))
    
    # 執行 INSERT SQL 語句
    exec_sql(
        "INSERT INTO todos (task, category, status, user_id) VALUES (%s, %s, %s, %s)",
        (task, category, "未完成", g.user["id"])
    )
    return redirect(url_for("index"))
```


### | ⚙️ Setup:
#### 1. 💻 Installation 
Install the necessary Python packages in `requirements.txt`.
```bash
pip install -r requirements.txt
```
#### 2. 🔑 Environment Variables
Create a .env file in the project root directory to store your database configuration and secret key. Replace the placeholder values with your actual MySQL credentials.
```env
# Flask secret key (for sessions, CSRF protection, etc.)
SECRET_KEY= your_secure_secret_key  

# MySQL database configuration
MYSQL_HOST = your_host_ip_or_domain
MYSQL_PORT = 3306
MYSQL_USER = your_mysql_username
MYSQL_PASSWORD = ""          
MYSQL_DB = "todolist"         
MYSQL_CURSORCLASS = DictCursor
MYSQL_CHARSET = utf8mb4
```
#### 3. ▶ How to Run
After setting up the database and installing dependencies, run the application:
```python
py app.py
```




