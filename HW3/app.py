# ==============================
#  app.py — Flask + MongoDB Template
#  功能：
#   1. 首頁顯示 index.html（輸入與上傳介面）
#   2. /api/add  新增單筆資料
#   3. /api/bulk 批次匯入 CSV/JSON (insert_many)
#   4. /api/all  顯示所有資料
# ==============================

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
import json
import csv
import io

# --- 初始化 Flask ---
app = Flask(__name__, template_folder="templates")
CORS(app)

# --- MongoDB 連線設定 ---
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URI)
db = client["travel_journal"]        # 資料庫名稱
collection = db["trips"]             # 集合名稱

# --- 首頁 ---
@app.route("/")
def home():
    return render_template("index.html")

# === 1️⃣ 新增單筆資料 ===
@app.route("/api/add", methods=["POST"])
def add_one():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No JSON data provided"}), 400
    collection.insert_one(data)
    return jsonify({"ok": True, "message": "Data added successfully"})

# === 2️⃣ 批次匯入 CSV/JSON (insert_many) ===
@app.route("/api/bulk", methods=["POST"])
def bulk_insert():
    try:
        # JSON body
        if request.content_type.startswith("application/json"):
            data = request.get_json()
        # File upload (CSV / JSON)
        elif "file" in request.files:
            file = request.files["file"]
            if file.filename.endswith(".csv"):
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream)
                data = list(reader)
            elif file.filename.endswith(".json"):
                data = json.load(file)
            else:
                return jsonify({"ok": False, "error": "Only CSV or JSON allowed"}), 400
        else:
            return jsonify({"ok": False, "error": "No data provided"}), 400

        if not isinstance(data, list):
            return jsonify({"ok": False, "error": "Data must be a list"}), 400

        result = collection.insert_many(data)
        return jsonify({"ok": True, "inserted": len(result.inserted_ids)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# === 3️⃣ 查詢所有資料 ===
@app.route("/api/all", methods=["GET"])
def get_all():
    data = list(collection.find({}, {"_id": 0}))
    return jsonify(data)

# === 主程式啟動 ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
