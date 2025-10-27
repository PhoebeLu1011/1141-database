# config.py
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['local']  # Replace with your database name
collection = db['startup_log']  # Replace with your collection name
