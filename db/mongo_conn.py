import pandas as pd
from pymongo import MongoClient

from config import MONGO_URL, MONGO_DB

def get_mongo_data():
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    cursor = db["User_Reviews"].find(
        {},
        {
            "appid": 1,
            "recommended": 1,
            "author.playtime_forever": 1,
            "timestamp_created": 1,
            "_id": 0
        }
    )
    df = pd.DataFrame(list(cursor))
    client.close()
    return df

if __name__ == "__main__":
    df = get_mongo_data()
    print(f"MongoDB OK — {len(df)} rows")
    print(df.head())