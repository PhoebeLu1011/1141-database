# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient, ASCENDING, UpdateOne
from dotenv import load_dotenv
import os, io
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # ← 新增

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")

# ---- Mongo 連線與資料庫 ----
mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/medical_db")
client = MongoClient(mongo_uri)
db = client.get_default_database()

# 建立複合唯一索引，避免重複與加速查詢
db.vitals.create_index([("patient_id", ASCENDING), ("ts", ASCENDING)], unique=True)

TAIPEI = ZoneInfo("Asia/Taipei")  # ← 新增：固定用台北時區

def _q_time_from_local_iso(s: str):
    """表單 datetime-local（本地台北）→ UTC datetime（查詢用）"""
    if not s:
        return None
    dt = datetime.fromisoformat(s)  # naive
    return dt.replace(tzinfo=TAIPEI).astimezone(timezone.utc)

def _maybe_range(field_min, field_max):
    cond = {}
    if field_min not in (None, "",):
        try: cond["$gte"] = float(field_min)
        except: pass
    if field_max not in (None, "",):
        try: cond["$lte"] = float(field_max)
        except: pass
    return cond or None

def _build_query_from_form(form):
    q = {}
    pid = (form.get("q_patient_id") or "").strip()
    if pid:
        q["patient_id"] = pid

    s = _q_time_from_local_iso(form.get("q_start"))
    e = _q_time_from_local_iso(form.get("q_end"))
    if s or e:
        q["ts"] = {}
        if s: q["ts"]["$gte"] = s
        if e: q["ts"]["$lt"]  = e

    for k, mongo_field in [
        ("q_hr", "hr"), ("q_bp_sys", "bp_sys"), ("q_bp_dia", "bp_dia"),
        ("q_spo2", "spo2"), ("q_temp", "temp")
    ]:
        rng = _maybe_range(form.get(f"{k}_min"), form.get(f"{k}_max"))
        if rng:
            q[mongo_field] = rng
    return q
# ---- 工具函式 ----
def to_num(x):
    """把表單字串/CSV NaN 轉成 float 或 None。"""
    try:
        if pd.isna(x):
            return None
        if isinstance(x, str) and x.strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def to_local_pair(dt_utc):
    """
    UTC -> 台北時間，回傳：
      (1) 表格顯示用: 'YYYY/MM/DD HH:MM'
      (2) <input type="datetime-local"> 用: 'YYYY-MM-DDTHH:MM'
    """
    if not dt_utc:
        return "", ""
    try:
        local = dt_utc.astimezone(TAIPEI)
        return local.strftime("%Y/%m/%d %H:%M"), local.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return "", ""


def parse_local_iso_to_utc(ts_raw: str):
    """
    解析 <input type="datetime-local"> 的字串 (YYYY-MM-DDTHH:MM) 為 UTC datetime。
    這個輸入是「本地時間(台北)」，先標上台北時區再轉 UTC。
    """
    try:
        if not ts_raw:
            return None
        naive = datetime.fromisoformat(ts_raw)         # 無時區
        local = naive.replace(tzinfo=TAIPEI)           # 標為台北
        return local.astimezone(timezone.utc)          # 轉 UTC
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
    # 撈最近 50 筆並附上本地時間雙格式
    rows_raw = list(db.vitals.find({}, {"_id": 0}).sort("ts", -1).limit(50))
    rows = []
    for r in rows_raw:
        ts = r.get("ts")
        ts_local_str, ts_local_iso = to_local_pair(ts)
        rows.append({
            "patient_id": r.get("patient_id", ""),
            "ts_local_str": ts_local_str,  # 表格顯示
            "ts_local_iso": ts_local_iso,  # 表單回填
            "hr": r.get("hr"),
            "bp_sys": r.get("bp_sys"),
            "bp_dia": r.get("bp_dia"),
            "spo2": r.get("spo2"),
            "temp": r.get("temp"),
        })
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
        ts_col = "timestamp" if "timestamp" in df.columns else ("ts" if "ts" in df.columns else None)
        if not ts_col:
            flash("CSV 需包含 timestamp 或 ts 欄位")
            return redirect(url_for("upload"))

        ts_series = pd.to_datetime(df[ts_col], errors="coerce")

        ops, skipped = [], 0
        for i, r in df.iterrows():
            pid_raw = r.get("patient_id")
            if pd.isna(pid_raw) or not str(pid_raw).strip():
                skipped += 1
                continue
            ts = ts_series.iloc[i]
            if pd.isna(ts):
                skipped += 1
                continue

            # 統一存 UTC
            if ts.tzinfo is None:
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
            ops.append(UpdateOne({"patient_id": pid, "ts": doc["ts"]}, {"$set": doc}, upsert=True))

        if ops:
            db.vitals.bulk_write(ops, ordered=False)

        flash(f"已匯入 {len(ops)} 筆記錄，跳過 {skipped} 筆（缺欄或時間格式不符）")
        return redirect(url_for("home"))

    return render_template("upload.html")


@app.route("/api/vitals/<patient_id>")
def api_vitals(patient_id):
    """
    支援 ?start=YYYY-MM-DDTHH:MM[:SS] / ?end=...
    若無時區，視為台北時間並轉 UTC 查詢。
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
                dt = dt.replace(tzinfo=TAIPEI)
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



@app.route("/demo", methods=["GET", "POST"])
def demo():
    find_results = None
    update_info = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "find":
            q = _build_query_from_form(request.form)
            cur = db.vitals.find(q, {"_id": 0}).sort("ts", ASCENDING).limit(200)
            find_results = list(cur)

        elif action == "update":
            q = _build_query_from_form(request.form)

            # 準備 $set / $inc（僅對有填值的欄位更新）
            set_fields = {
                "hr": to_num(request.form.get("u_hr")),
                "bp_sys": to_num(request.form.get("u_bp_sys")),
                "bp_dia": to_num(request.form.get("u_bp_dia")),
                "spo2": to_num(request.form.get("u_spo2")),
                "temp": to_num(request.form.get("u_temp")),
                "status": (request.form.get("u_status") or "").strip() or None,
                "note": (request.form.get("u_note") or "").strip() or None,
            }
            inc_fields = {
                "hr": to_num(request.form.get("u_hr_inc")),
                "bp_sys": to_num(request.form.get("u_bp_sys_inc")),
                "bp_dia": to_num(request.form.get("u_bp_dia_inc")),
                "spo2": to_num(request.form.get("u_spo2_inc")),
                "temp": to_num(request.form.get("u_temp_inc")),
            }

            update_doc = {}
            # 只留下不是 None / 空字串的欄位
            set_payload = {k:v for k,v in set_fields.items() if v is not None}
            inc_payload = {k:v for k,v in inc_fields.items() if v not in (None, 0)}
            if set_payload: update_doc["$set"] = set_payload
            if inc_payload: update_doc["$inc"] = inc_payload

            if not update_doc:
                flash("沒有可更新的欄位（$set/$inc 都是空）")
                return redirect(url_for("demo"))

            # 更新前筆數
            before = db.vitals.count_documents(q)
            res = db.vitals.update_many(q, update_doc)
            after = db.vitals.count_documents(q)

            # 抽樣 20 筆看更新後結果
            sample = list(db.vitals.find(q, {"_id":0}).sort("ts", ASCENDING).limit(20))

            update_info = type("U", (), {})()
            update_info.matched = res.matched_count
            update_info.modified = res.modified_count
            update_info.before = before
            update_info.after = after
            update_info.sample = sample

    return render_template("demo.html",
                           find_results=find_results,
                           update_info=update_info)

if __name__ == "__main__":
    app.run(debug=True)
