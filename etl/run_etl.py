"""
One-shot ETL for the Steam Analytics OLAP stack.

Reads the raw Kaggle CSVs mounted at /data/raw (steam.csv and
steam_reviews.csv) and populates:

- MySQL  `steam_katalog.clean_mysql_katalog` — game catalog + aggregate ratings
- Mongo  `Steams_Analytics.Steams_Tags_Genre` — per-game SteamSpy tags (incl. "Indie")
- Mongo  `Steams_Analytics.User_Reviews`      — sample of individual user reviews

Equivalent to running Python Script/python_script.ipynb +
fix_mysql_ratings.py + fix_etl_mongo.py + the (missing) tags ETL in one pass.
"""

import os
import time

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

RAW_DIR = "/data/raw"
MYSQL_URL = os.environ["MYSQL_URL"]
MONGO_URL = os.environ["MONGO_URL"]
MONGO_DB = os.environ.get("MONGO_DB", "Steams_Analytics")

# Sampling targets for User_Reviews — keeps the ETL fast while still giving
# Q3 (retention) a usable spread of games and review volume.
TARGET_GAMES = 150
MAX_PER_GAME = 800
CHUNK_SIZE = 200_000
MAX_CHUNKS = 50

REVIEW_COLS = [
    "app_id",
    "app_name",
    "review_id",
    "language",
    "recommended",
    "timestamp_created",
    "author.playtime_forever",
]


def wait_for_mysql(engine, retries=30, delay=2):
    for _ in range(retries):
        try:
            with engine.connect():
                return
        except OperationalError:
            time.sleep(delay)
    raise RuntimeError("MySQL not reachable")


def wait_for_mongo(client, retries=30, delay=2):
    for _ in range(retries):
        try:
            client.admin.command("ping")
            return
        except ConnectionFailure:
            time.sleep(delay)
    raise RuntimeError("MongoDB not reachable")


def load_mysql_catalog(engine):
    print("Reading steam.csv ...")
    df = pd.read_csv(f"{RAW_DIR}/steam.csv")

    cols = [
        "appid", "name", "release_date", "price", "developer", "publisher",
        "positive_ratings", "negative_ratings",
    ]
    df_katalog = df[cols].dropna()
    df_katalog.to_sql("clean_mysql_katalog", engine, if_exists="replace", index=False)
    print(f"  -> clean_mysql_katalog: {len(df_katalog):,} rows")
    return df


def load_tags_genre(df_steam, mongo_db):
    print("Building Steams_Tags_Genre from steamspy_tags ...")
    tagged = df_steam[["appid", "steamspy_tags"]].dropna()
    docs = [
        {"appid": int(row.appid), "tags": [t for t in str(row.steamspy_tags).split(";") if t]}
        for row in tagged.itertuples()
    ]

    col = mongo_db["Steams_Tags_Genre"]
    col.drop()
    if docs:
        col.insert_many(docs)
    print(f"  -> Steams_Tags_Genre: {len(docs):,} docs")


def load_user_reviews(mongo_db):
    print(f"Reading steam_reviews.csv in chunks of {CHUNK_SIZE:,} (this can take a while)...")
    per_game_counts = {}
    collected = []

    reader = pd.read_csv(f"{RAW_DIR}/steam_reviews.csv", usecols=REVIEW_COLS, chunksize=CHUNK_SIZE)
    for i, chunk in enumerate(reader):
        if i >= MAX_CHUNKS:
            print(f"  Hard cap {MAX_CHUNKS} chunks reached — stopping.")
            break

        chunk = chunk.rename(columns={"app_id": "appid"})
        chunk["appid"] = pd.to_numeric(chunk["appid"], errors="coerce")
        chunk = chunk.dropna(subset=["appid", "timestamp_created"])
        chunk["appid"] = chunk["appid"].astype(int)

        for appid, group in chunk.groupby("appid"):
            already = per_game_counts.get(appid, 0)
            if appid not in per_game_counts and len(per_game_counts) >= TARGET_GAMES:
                continue
            remaining = MAX_PER_GAME - already
            if remaining <= 0:
                continue
            sample = group.head(remaining)
            per_game_counts[appid] = already + len(sample)
            collected.append(sample)

        print(f"  chunk {i + 1}: {len(per_game_counts)} games, {sum(per_game_counts.values()):,} rows")
        if len(per_game_counts) >= TARGET_GAMES:
            print("  Target reached — stopping.")
            break

    if not collected:
        print("  No review rows collected — check /data/raw/steam_reviews.csv")
        return

    df = pd.concat(collected, ignore_index=True)
    col = mongo_db["User_Reviews"]
    col.drop()
    col.insert_many(df.to_dict("records"), ordered=False)
    print(f"  -> User_Reviews: {len(df):,} docs, {df['appid'].nunique()} unique appids")


def main():
    engine = create_engine(MYSQL_URL)
    wait_for_mysql(engine)

    client = MongoClient(MONGO_URL)
    wait_for_mongo(client)
    mongo_db = client[MONGO_DB]

    df_steam = load_mysql_catalog(engine)
    load_tags_genre(df_steam, mongo_db)
    load_user_reviews(mongo_db)

    engine.dispose()
    client.close()
    print("ETL done.")


if __name__ == "__main__":
    main()
