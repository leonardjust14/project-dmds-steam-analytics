from pymongo import MongoClient
from db.config import MONGO_URL, MONGO_DB
client = MongoClient(MONGO_URL)
db = client[MONGO_DB]

pipeline = [
    {"$group": {"_id": "$appid", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 10}
]
result = list(db["User_Reviews"].aggregate(pipeline))
print("Top appids by review count:")
for r in result:
    print(r)
client.close()
