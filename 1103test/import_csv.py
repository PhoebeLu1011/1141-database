import os, glob
import pandas as pd
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError
from dotenv import load_dotenv

load_dotenv()

# 建議在 MONGO_URI 裡面就帶 DB 名稱，例如 mongodb://127.0.0.1:27017/medical_db
uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/medical_db")
client = MongoClient(uri)

# 若 URI 沒帶 DB 名稱，改用預設 medical_db
db = client.get_default_database() or client["medical_db"]

def _num(x):
    try:
        return None if pd.isna(x) else float(x)
    except Exception:
        return None

def upsert_df(df: pd.DataFrame):
    # 統一時間欄位名稱
    if "timestamp" in df.columns:
        ts_series = pd.to_datetime(df["timestamp"])
    elif "ts" in df.columns:
        ts_series = pd.to_datetime(df["ts"])
    else:
        raise ValueError("CSV 需包含 timestamp 或 ts 欄位")

    ops = []
    for i, r in df.iterrows():
        ts = ts_series.iloc[i].to_pydatetime()
        pid = str(r.get("patient_id"))
        doc = {
            "patient_id": pid,
            "ts": ts,
            "hr": _num(r.get("hr")),
            "bp_sys": _num(r.get("bp_sys")),
            "bp_dia": _num(r.get("bp_dia")),
            "spo2": _num(r.get("spo2")),
            "temp": _num(r.get("temp")),
        }
        ops.append(
            UpdateOne({"patient_id": pid, "ts": ts}, {"$set": doc}, upsert=True)
        )

    if ops:
        try:
            db.vitals.bulk_write(ops, ordered=False)
        except BulkWriteError as e:
            # 便於除錯：印出第一個錯誤
            print("BulkWriteError:", e.details.get("writeErrors", [])[0])

if __name__ == "__main__":
    # 建議先建立索引（只需執行一次）
    db.vitals.create_index([("patient_id", 1), ("ts", 1)], unique=True)
    db.vitals.create_index([("ts", -1)])

    for path in glob.glob("data/*.csv"):
        df = pd.read_csv(path)
        upsert_df(df)
        print("imported:", path)
