## 1141 - Database Systems
## HW1- 
### Goal:
### Project Structure:
```
HW1/
├── app.py # MAIN
├── templates/ # HTML
│ ├── index.html 
│ ├── login.html 
│ └── edit.html 
└── .env
```
### Setup:
####  Environment Variables
Create a `.env` file in the project root directory to store your database configuration and secret key.
```env
# Flask secret key (for sessions, CSRF protection, etc.)
SECRET_KEY= ""  

# MySQL database configuration
MYSQL_HOST = ""
MYSQL_PORT = 
MYSQL_USER = ""
MYSQL_PASSWORD = ""          
MYSQL_DB = "todolist"         # ← 先建好 DB
MYSQL_CURSORCLASS = ""
MYSQL_CHARSET = ""
```
#### ▶️ How to Run
```python
py app.py
```

