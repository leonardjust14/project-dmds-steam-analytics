import pandas as pd
from sqlalchemy import create_engine, text

from db.config import MYSQL_URL

ENGINE = create_engine(MYSQL_URL)

# Load ratings dari steam.csv
ratings = pd.read_csv(
    "C:/Project PDDS/steam.csv/steam.csv",
    usecols=["appid", "positive_ratings", "negative_ratings"],
).rename(columns={"positive_ratings": "pos", "negative_ratings": "neg"})
print(f"Loaded {len(ratings)} rows from steam.csv")

with ENGINE.connect() as conn:
    # 1. Tambah kolom kalau belum ada
    for col, dtype in [("positive_ratings", "INT DEFAULT 0"), ("negative_ratings", "INT DEFAULT 0")]:
        try:
            conn.execute(text(f"ALTER TABLE clean_mysql_katalog ADD COLUMN {col} {dtype}"))
            conn.commit()
            print(f"Column {col} added")
        except Exception:
            conn.rollback()
            print(f"Column {col} already exists, skipping")

    # 2. Load ratings ke temp table
    conn.execute(text("DROP TABLE IF EXISTS _ratings_tmp"))
    conn.execute(text(
        "CREATE TEMPORARY TABLE _ratings_tmp "
        "(appid INT PRIMARY KEY, pos INT, neg INT)"
    ))
    conn.commit()

    # Bulk insert ke temp table
    rows = [{"appid": int(r.appid), "pos": int(r.pos), "neg": int(r.neg)} for r in ratings.itertuples()]
    conn.execute(
        text("INSERT INTO _ratings_tmp (appid, pos, neg) VALUES (:appid, :pos, :neg)"),
        rows,
    )
    conn.commit()
    print("Temp table populated")

    # 3. Single JOIN-based UPDATE
    conn.execute(text(
        "UPDATE clean_mysql_katalog k "
        "JOIN _ratings_tmp t ON k.appid = t.appid "
        "SET k.positive_ratings = t.pos, k.negative_ratings = t.neg"
    ))
    conn.commit()
    print("Bulk update done")

    # Verify
    result = conn.execute(text(
        "SELECT appid, name, price, positive_ratings, negative_ratings "
        "FROM clean_mysql_katalog WHERE positive_ratings > 0 LIMIT 5"
    ))
    for r in result:
        print(r)

ENGINE.dispose()
print("Done!")
