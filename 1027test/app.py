# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient, ASCENDING, UpdateOne
from dotenv import load_dotenv
import os, io
import pandas as pd
from datetime import datetime, timezone

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")

# ---- Mongo 連線與資料庫 ----
mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/medical_db")
client = MongoClient(mongo_uri)
db = client.get_default_database()

# 建立複合唯一索引，避免重複與加速查詢
db.vitals.create_index([("patient_id", ASCENDING), ("ts", ASCENDING)], unique=True)

# ---- 工具函式 ----
def to_num(x):
    """把表單字串/CSV NaN 轉成 float 或 None。"""
    try:
        # pandas NaN
        if pd.isna(x):
            return None
        # 空字串
        if isinstance(x, str) and x.strip() == "":
            return None
        return float(x)
    except Exception:
        return None

def parse_local_iso_to_utc(ts_raw: str):
    """
    解析 <input type="datetime-local"> 的字串 (YYYY-MM-DDTHH:MM) 為 UTC datetime。
    假設輸入是『本地時間』，以本地時區轉為 UTC 儲存。
    若你只需要 naive，本函式可改回 datetime.fromisoformat(ts_raw)。
    """
    try:
        # 無時區的本地時間
        naive = datetime.fromisoformat(ts_raw)
        # 這裡可依你的伺服器/使用者時區調整；若伺服器位於台灣：
        local = naive.replace(tzinfo=timezone.utc).astimezone()  # 若系統有正確時區
        # 更保險的方法：明確寫台北時區，需安裝 pytz 或 zoneinfo (py>=3.9)
        # from zoneinfo import ZoneInfo
        # local = naive.replace(tzinfo=ZoneInfo("Asia/Taipei"))
        return local.astimezone(timezone.utc)
    except Exception:
        return None

# ---- Routes ----
@app.post("/quick_add")
def quick_add():
    pid = (request.form.get("patient_id") or "").strip()
    ts_raw = request.form.get("timestamp", "").strip()

    if not pid or not ts_raw:
        flash("缺少必要欄位：patient_id / timestamp")
        return redirect(request.referrer or url_for("home"))

    ts = parse_local_iso_to_utc(ts_raw)
    if not ts:
        flash("時間格式不正確（YYYY-MM-DDTHH:MM）")
        return redirect(request.referrer or url_for("home"))

    doc = {
        "patient_id": pid,
        "ts": ts,
        "hr": to_num(request.form.get("hr")),
        "bp_sys": to_num(request.form.get("bp_sys")),
        "bp_dia": to_num(request.form.get("bp_dia")),
        "spo2": to_num(request.form.get("spo2")),
        "temp": to_num(request.form.get("temp")),
    }

    db.vitals.update_one({"patient_id": pid, "ts": ts}, {"$set": doc}, upsert=True)
    flash(f"已寫入：{pid} @ {ts.isoformat()}")
    return redirect(request.referrer or url_for("home"))

@app.route("/")
def home():
    rows = list(
        db.vitals.find({}, {"_id": 0}).sort("ts", -1).limit(50)
    )
    return render_template("list.html", rows=rows)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("請上傳 CSV 檔")
            return redirect(url_for("upload"))

        df = pd.read_csv(io.BytesIO(f.read()))

        # 正規化時間欄位
        ts_col = None
        if "timestamp" in df.columns:
            ts_col = "timestamp"
        elif "ts" in df.columns:
            ts_col = "ts"
        if not ts_col:
            flash("CSV 需包含 timestamp 或 ts 欄位")
            return redirect(url_for("upload"))

        # 嘗試解析成 datetime；coerce 可避免整檔報錯
        ts_series = pd.to_datetime(df[ts_col], errors="coerce")

        ops = []
        skipped = 0

        for i, r in df.iterrows():
            pid_raw = r.get("patient_id")
            # 跳過缺少 patient_id 或 ts 無法解析的列
            if pd.isna(pid_raw) or not str(pid_raw).strip():
                skipped += 1
                continue
            ts = ts_series.iloc[i]
            if pd.isna(ts):
                skipped += 1
                continue

            # 統一儲存為 UTC（若 ts 是 naive，設為本地再轉 UTC；或直接當作 UTC）
            if ts.tzinfo is None:
                # 看需求：若CSV時間視為本地時間，需轉 UTC；若已經是 UTC 就直接 replace
                ts = ts.tz_localize("Asia/Taipei").tz_convert("UTC")
            else:
                ts = ts.tz_convert("UTC")

            pid = str(pid_raw).strip()
            doc = {
                "patient_id": pid,
                "ts": ts.to_pydatetime(),
                "hr": to_num(r.get("hr")),
                "bp_sys": to_num(r.get("bp_sys")),
                "bp_dia": to_num(r.get("bp_dia")),
                "spo2": to_num(r.get("spo2")),
                "temp": to_num(r.get("temp")),
            }
            ops.append(
                UpdateOne(
                    {"patient_id": pid, "ts": doc["ts"]},
                    {"$set": doc},
                    upsert=True
                )
            )

        if ops:
            db.vitals.bulk_write(ops, ordered=False)

        flash(f"已匯入 {len(ops)} 筆記錄，跳過 {skipped} 筆（缺欄或時間格式不符）")
        return redirect(url_for("home"))

    return render_template("upload.html")

@app.route("/api/vitals/<patient_id>")
def api_vitals(patient_id):
    """
    支援 ?start=YYYY-MM-DDTHH:MM[:SS] / ?end=...
    以 ISO8601（建議含時區）查詢；若無時區，視為本地時間並轉 UTC 查。
    """
    start = request.args.get("start")
    end = request.args.get("end")

    q = {"patient_id": patient_id}

    def _parse_query_time(s: str):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # 視為本地轉 UTC（或依需求直接當作 UTC）
                dt = dt.replace(tzinfo=timezone.utc).astimezone()
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    s_dt = _parse_query_time(start)
    e_dt = _parse_query_time(end)

    if s_dt or e_dt:
        q["ts"] = {}
        if s_dt: q["ts"]["$gte"] = s_dt
        if e_dt: q["ts"]["$lt"] = e_dt

    cur = db.vitals.find(q, {"_id": 0}).sort("ts", ASCENDING)
    return jsonify(list(cur))

@app.route("/chart/<patient_id>")
def chart(patient_id):
    return render_template("chart.html", patient_id=patient_id)

if __name__ == "__main__":
    app.run(debug=True)
