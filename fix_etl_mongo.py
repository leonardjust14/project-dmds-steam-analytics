"""
Re-ETL untuk MongoDB User_Reviews — versi stratified.

Masalah versi sebelumnya: ambil 200 appid pertama yang ketemu di CSV secara
berurutan -> 218 Paid vs cuma 3 Free-to-Play. Perbandingan FTP vs Paid di Q3
jadi tidak meaningful (n=3).

Fix ini:
- Ambil daftar appid Free-to-Play (price == 0) dari MySQL clean_mysql_katalog
- Baca CSV in chunks, klasifikasikan tiap appid sebagai FTP atau Paid
- Kumpulkan sampai TARGET_FTP_GAMES game FTP dan TARGET_PAID_GAMES game Paid
  tercapai (atau hard cap baris/chunk tercapai)
- Include timestamp_created untuk retention analysis Q3
- Drop collection lama, insert yang baru langsung ke MongoDB
"""

import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine

from db.config import MYSQL_URL, MONGO_URL, MONGO_DB

CSV_PATH = r"C:\Project PDDS\steam_reviews.csv\steam_reviews.csv"
COLLECTION = "User_Reviews"

CHUNK_SIZE = 200_000
MAX_PER_GAME = 800        # max review per appid
TARGET_FTP_GAMES = 40     # target appid unik kategori Free-to-Play
TARGET_PAID_GAMES = 160   # target appid unik kategori Paid
MAX_CHUNKS = 40           # hard cap jumlah chunk (40 * 200K = 8M baris discan)

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
    print(f"  {len(ftp_appids):,} appid Free-to-Play ditemukan di MySQL")

    per_game_counts = {}     # appid -> berapa row sudah dikumpulkan
    game_category = {}       # appid -> "FTP" / "Paid"
    collected = []
    n_ftp_games = 0
    n_paid_games = 0

    print(f"\nMembaca {CSV_PATH} in chunks of {CHUNK_SIZE:,}...")
    reader = pd.read_csv(CSV_PATH, usecols=COLS, chunksize=CHUNK_SIZE)

    for i, chunk in enumerate(reader):
        if i >= MAX_CHUNKS:
            print(f"  Hard cap {MAX_CHUNKS} chunk tercapai — berhenti.")
            break

        chunk = chunk.rename(columns={"app_id": "appid"})
        chunk["appid"] = pd.to_numeric(chunk["appid"], errors="coerce")
        chunk = chunk.dropna(subset=["appid"])
        chunk["appid"] = chunk["appid"].astype(int)

        for appid, group in chunk.groupby("appid"):
            category = "FTP" if appid in ftp_appids else "Paid"

            is_new_game = appid not in per_game_counts
            if is_new_game:
                if category == "FTP" and n_ftp_games >= TARGET_FTP_GAMES:
                    continue
                if category == "Paid" and n_paid_games >= TARGET_PAID_GAMES:
                    continue

            already = per_game_counts.get(appid, 0)
            remaining_quota = MAX_PER_GAME - already
            if remaining_quota <= 0:
                continue

            sample = group.head(remaining_quota)
            per_game_counts[appid] = already + len(sample)
            game_category[appid] = category
            collected.append(sample)

            if is_new_game:
                if category == "FTP":
                    n_ftp_games += 1
                else:
                    n_paid_games += 1

        total_rows = sum(per_game_counts.values())
        print(
            f"  Chunk {i+1:>3}: {n_ftp_games} game FTP, {n_paid_games} game Paid, "
            f"{total_rows:,} baris terkumpul"
        )

        if n_ftp_games >= TARGET_FTP_GAMES and n_paid_games >= TARGET_PAID_GAMES:
            print("  Target tercapai — berhenti baca CSV.")
            break

    if not collected:
        print("Tidak ada data terkumpul. Cek path CSV.")
        return

    df = pd.concat(collected, ignore_index=True)
    print(f"\nTotal rows: {len(df):,} dari {len(per_game_counts)} appid")
    print(f"  FTP games: {n_ftp_games}, Paid games: {n_paid_games}")
    print(f"timestamp_created null: {df['timestamp_created'].isna().sum()}")

    # ── Insert ke MongoDB ──────────────────────────────────────────────────────
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    col = db[COLLECTION]

    print(f"\nDrop collection lama '{COLLECTION}'...")
    col.drop()

    records = df.to_dict("records")
    print(f"Inserting {len(records):,} dokumen ke MongoDB...")
    col.insert_many(records, ordered=False)
    client.close()

    print(f"\nSelesai. {len(records):,} dokumen berhasil diinsert.")
    print(f"Appid unik: {df['appid'].nunique()}")
    print("\nTop 10 appid by review count:")
    print(df.groupby("app_name")["appid"].count().nlargest(10))


if __name__ == "__main__":
    run()
