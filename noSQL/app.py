from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, GEO2D
from dotenv import load_dotenv
from bson import ObjectId
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

# === 連接 MongoDB ===
mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/travelmap")
client = MongoClient(mongo_uri)
db = client["travelmap"]
entries = db["entries"]
entries.create_index([("location", "2dsphere")])


def to_json(doc):
    # 轉 _id / date 成可 JSON 化
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "date" in doc and isinstance(doc["date"], datetime):
        doc["date"] = doc["date"].isoformat()
    if "createdAt" in doc and isinstance(doc["createdAt"], datetime):
        doc["createdAt"] = doc["createdAt"].isoformat()
    return doc

# === 首頁（Leaflet 地圖） ===
@app.route("/")
def home():
    return render_template("map.html")

# === 建立紀錄 ===
@app.route("/api/entries", methods=["GET"])
def get_entries():
    bbox = request.args.get("bbox")
    if not bbox:
        docs = list(entries.find().sort("createdAt", -1).limit(200))
    else:
        try:
            min_lng, min_lat, max_lng, max_lat = map(float, bbox.split(","))
        except Exception:
            return jsonify({"error": "bbox 參數無效"}), 400
        docs = list(entries.find({
            "location": {"$geoWithin": {"$box": [[min_lng, min_lat], [max_lng, max_lat]]}}
        }).limit(1000))
    return jsonify([to_json(d) for d in docs])

# === 查詢附近紀錄 ===
@app.route("/api/entries/near", methods=["GET"])
def get_nearby_entries():
    try:
        lng = float(request.args.get("lng"))
        lat = float(request.args.get("lat"))
        max_distance = float(request.args.get("maxDistance", 3000))
    except Exception:
        return jsonify({"error": "無效的經緯度"}), 400

    docs = list(entries.find({
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": max_distance
            }
        }
    }).limit(200))

    return jsonify([to_json(d) for d in docs])   # ✅ 用 to_json


# === 更新既有紀錄（目前支援：改座標、標題、筆記、照片） ===
@app.route("/api/entries/<id>", methods=["PATCH"])
def update_entry(id):
    body = request.get_json() or {}
    update = {}
    if "title" in body: update["title"] = body["title"]
    if "notes" in body: update["notes"] = body["notes"]
    if "photos" in body: update["photos"] = body["photos"]
    # 移動座標
    lng = body.get("lng")
    lat = body.get("lat")
    if lng is not None and lat is not None:
        update["location"] = {"type": "Point", "coordinates": [float(lng), float(lat)]}
    if not update:
        return jsonify({"error": "沒有可更新的欄位"}), 400

    res = entries.update_one({"_id": ObjectId(id)}, {"$set": update})
    if res.matched_count == 0:
        return jsonify({"error": "找不到該筆"}), 404
    doc = entries.find_one({"_id": ObjectId(id)})
    doc["_id"] = str(doc["_id"])
    return jsonify(doc), 200


# === 刪除紀錄 ===
@app.route("/api/entries/<id>", methods=["DELETE"])
def delete_entry(id):
    res = entries.delete_one({"_id": ObjectId(id)})
    if res.deleted_count == 0:
        return jsonify({"error": "找不到該筆"}), 404
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
