"""
Phase 2 (v2) — cari game Free-to-Play di steam_reviews.csv.

Phase 1 sudah insert 80,100 dokumen (101 game, semua Paid) ke MongoDB
User_Reviews dari range alfabet awal CSV ("20XX".."Banished") - 0 FTP.

Pendekatan v2: single pass dari awal file, filter VEKTORIZED (isin) ke
appid Free-to-Play saja (skip pemrosesan game Paid sama sekali, jauh lebih
cepat daripada groupby). Append hasil ke collection yang sudah ada.
"""

import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine

from db.config import MYSQL_URL, MONGO_URL, MONGO_DB

CSV_PATH = r"C:\Project PDDS\steam_reviews.csv\steam_reviews.csv"
COLLECTION = "User_Reviews"

CHUNK_SIZE = 500_000
MAX_PER_GAME = 800
TARGET_FTP_GAMES = 15
MAX_CHUNKS = 200  # safety cap (200 * 500K = 100M rows, lebih dari cukup utk full file)

COLS = [
    "app_id",
    "app_name",
    "review_id",
    "language",
    "recommended",
    "timestamp_created",
    "author.playtime_forever",
]


def run():
    print("Mengambil daftar appid Free-to-Play dari MySQL...")
    engine = create_engine(MYSQL_URL)
    catalog = pd.read_sql("SELECT appid, price FROM clean_mysql_katalog", engine)
    engine.dispose()
    ftp_appids = set(catalog.loc[catalog["price"] == 0, "appid"].tolist())
    print(f"  {len(ftp_appids):,} appid Free-to-Play ditemukan di MySQL", flush=True)

    per_game_counts = {}
    collected = []
    n_ftp_games = 0

    print(f"\nMembaca {CSV_PATH}, chunks of {CHUNK_SIZE:,} (vectorized FTP filter)...", flush=True)
    reader = pd.read_csv(CSV_PATH, usecols=COLS, chunksize=CHUNK_SIZE)

    for i, chunk in enumerate(reader):
        if i >= MAX_CHUNKS:
            print(f"  Hard cap {MAX_CHUNKS} chunk tercapai - berhenti.")
            break

        chunk = chunk.rename(columns={"app_id": "appid"})
        chunk["appid"] = pd.to_numeric(chunk["appid"], errors="coerce")
        chunk = chunk.dropna(subset=["appid"])
        chunk["appid"] = chunk["appid"].astype(int)

        ftp_chunk = chunk[chunk["appid"].isin(ftp_appids)]

        if not ftp_chunk.empty:
            for appid, group in ftp_chunk.groupby("appid"):
                is_new_game = appid not in per_game_counts
                if is_new_game and n_ftp_games >= TARGET_FTP_GAMES:
                    continue
                already = per_game_counts.get(appid, 0)
                remaining_quota = MAX_PER_GAME - already
                if remaining_quota <= 0:
                    continue
                sample = group.head(remaining_quota)
                per_game_counts[appid] = already + len(sample)
                collected.append(sample)
                if is_new_game:
                    n_ftp_games += 1

        total_rows = sum(per_game_counts.values())
        first_name = chunk["app_name"].iloc[0] if len(chunk) else "?"
        print(
            f"  Chunk {i+1:>3} (mulai '{first_name}'): {n_ftp_games} game FTP, "
            f"{total_rows:,} baris terkumpul",
            flush=True,
        )

        if n_ftp_games >= TARGET_FTP_GAMES:
            print("  Target tercapai - berhenti baca CSV.")
            break

    if not collected:
        print("Tidak ada data FTP terkumpul.")
        return

    df = pd.concat(collected, ignore_index=True)
    print(f"\nTotal rows baru: {len(df):,} dari {len(per_game_counts)} appid FTP")
    print(f"timestamp_created null: {df['timestamp_created'].isna().sum()}")
    print("\nGame FTP yang ditemukan:")
    print(df.groupby("app_name")["appid"].count())

    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    col = db[COLLECTION]

    records = df.to_dict("records")
    print(f"\nInserting {len(records):,} dokumen baru ke MongoDB (append)...")
    col.insert_many(records, ordered=False)
    client.close()

    print("Selesai.")


if __name__ == "__main__":
    run()
