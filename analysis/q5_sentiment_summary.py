import pandas as pd
from pymongo import MongoClient

from db.config import MONGO_URL, MONGO_DB


def build_sentiment_summary():
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]

    pipeline = [
        {
            "$group": {
                "_id": "$appid",
                "total_reviews": {"$sum": 1},
                "total_positive": {
                    "$sum": {
                        "$cond": [{"$eq": ["$recommended", True]}, 1, 0]
                    }
                },
                "avg_playtime_hours": {
                    "$avg": {
                        "$divide": [
                            {"$ifNull": [{"$getField": "author.playtime_forever"}, 0]},
                            60,
                        ]
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "appid": "$_id",
                "total_reviews": 1,
                "total_positive": 1,
                "positive_ratio": {
                    "$divide": ["$total_positive", "$total_reviews"]
                },
                "avg_playtime_hours": 1,
            }
        },
    ]

    results = list(db["User_Reviews"].aggregate(pipeline))

    col = db["Sentiment_Summary"]
    col.drop()
    if results:
        col.insert_many(results, ordered=False)

    client.close()
    print(f"Sentiment_Summary created: {len(results)} games")
    return results


def get_sentiment_summary():
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    cursor = db["Sentiment_Summary"].find({}, {"_id": 0})
    df = pd.DataFrame(list(cursor))
    client.close()
    return df


if __name__ == "__main__":
    results = build_sentiment_summary()
    df = pd.DataFrame(results)
    if not df.empty:
        print("\nTop 5 game by avg playtime sebelum review:")
        print(df.nlargest(5, "avg_playtime_hours")[["appid", "avg_playtime_hours", "positive_ratio"]])
