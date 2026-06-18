import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine

from db.config import MYSQL_URL, MONGO_URL, MONGO_DB

TIER_ORDER = ["Free", "$0–$5", "$5–$15", "$15–$30", "$30+"]


def price_tier(p):
    if p == 0:
        return "Free"
    elif p <= 5:
        return "$0–$5"
    elif p <= 15:
        return "$5–$15"
    elif p <= 30:
        return "$15–$30"
    else:
        return "$30+"


def get_engagement_data():
    """
    Q3: Retention Analysis — apakah game di price tier lebih tinggi mendapat ulasan aktif lebih panjang?

    Returns dict:
      - 'retention': per-game retention window (days), price category, review stats
      - 'playtime': per-playtime-bucket sentiment (dari review individual)
    """
    # MySQL: info game
    engine = create_engine(MYSQL_URL)
    mysql_df = pd.read_sql(
        "SELECT appid, name, price, release_date FROM clean_mysql_katalog",
        engine,
    )
    engine.dispose()
    mysql_df["release_date"] = pd.to_datetime(mysql_df["release_date"])
    mysql_df["price_category"] = mysql_df["price"].apply(price_tier)

    # MongoDB: ambil semua reviews dengan timestamp
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    # Note: "author.playtime_forever" is a flat key with a literal dot (from CSV ETL),
    # not a nested field — MongoDB projection treats dots as nested paths and skips it.
    # Fetch all fields and drop _id in Python instead.
    cursor = db["User_Reviews"].find(
        {},
        {"_id": 0},
    )
    reviews_raw = list(cursor)
    client.close()

    if not reviews_raw:
        return {"retention": pd.DataFrame(), "playtime": pd.DataFrame()}

    df = pd.DataFrame(reviews_raw)
    df["appid"] = pd.to_numeric(df["appid"], errors="coerce")
    df["timestamp_created"] = pd.to_numeric(df["timestamp_created"], errors="coerce")
    df = df.dropna(subset=["appid", "timestamp_created"])
    df["appid"] = df["appid"].astype(int)

    # Parse recommended (bisa string atau bool)
    df["recommended"] = df["recommended"].map(
        {"True": True, "False": False, True: True, False: False}
    )

    # Parse playtime dari nested author field (stored as string dalam ETL lama)
    def _playtime(val):
        if isinstance(val, (int, float)):
            return float(val) if val else 0.0
        if isinstance(val, dict):
            return float(val.get("playtime_forever", 0) or 0)
        return 0.0

    # Field stored as flat key "author.playtime_forever" (dot is literal, from CSV ETL)
    if "author.playtime_forever" in df.columns:
        df["playtime_hours"] = df["author.playtime_forever"].apply(_playtime) / 60
    elif "author" in df.columns:
        import ast
        df["playtime_hours"] = df["author"].apply(
            lambda x: float(ast.literal_eval(x).get("playtime_forever", 0) or 0) / 60
            if isinstance(x, str)
            else (float(x.get("playtime_forever", 0) or 0) / 60 if isinstance(x, dict) else 0)
        )
    else:
        df["playtime_hours"] = 0.0

    df["review_date"] = pd.to_datetime(df["timestamp_created"], unit="s", errors="coerce")

    # ── Retention per game ─────────────────────────────────────────────────────
    # min timestamp = first review ever, max = last review ever
    retention_agg = (
        df.groupby("appid")
        .agg(
            first_review=("review_date", "min"),
            last_review=("review_date", "max"),
            review_count=("recommended", "count"),
            positive_count=("recommended", "sum"),
        )
        .reset_index()
    )
    retention_agg["positive_ratio"] = retention_agg["positive_count"] / retention_agg["review_count"]

    # Join ke MySQL untuk release_date dan price
    ret = pd.merge(retention_agg, mysql_df[["appid", "name", "price", "release_date", "price_category"]], on="appid", how="inner")

    # Retention window = last_review - release_date (bukan last - first, itu lebih ke spread)
    ret["retention_days"] = (ret["last_review"] - ret["release_date"]).dt.days
    ret["active_days"] = (ret["last_review"] - ret["first_review"]).dt.days

    # Filter: hanya game yang punya setidaknya 10 review (biar meaningful)
    ret = ret[ret["review_count"] >= 10].copy()

    # ── Playtime bucket sentiment ──────────────────────────────────────────────
    def playtime_bucket(h):
        if h == 0:
            return "0 jam"
        elif h < 1:
            return "< 1 jam"
        elif h < 10:
            return "1-10 jam"
        elif h < 50:
            return "10-50 jam"
        elif h < 200:
            return "50-200 jam"
        else:
            return "200+ jam"

    df["playtime_bucket"] = df["playtime_hours"].apply(playtime_bucket)

    # Merge ke MySQL untuk price_category
    df_merged = pd.merge(df, mysql_df[["appid", "name", "price_category"]], on="appid", how="inner")

    playtime_stats = (
        df_merged.groupby(["playtime_bucket", "price_category"])
        .agg(
            total=("recommended", "count"),
            positive=("recommended", "sum"),
        )
        .reset_index()
    )
    playtime_stats["positive_ratio"] = playtime_stats["positive"] / playtime_stats["total"]

    return {"retention": ret, "playtime": playtime_stats}


if __name__ == "__main__":
    data = get_engagement_data()
    ret = data["retention"]
    print(f"Games dianalisis: {len(ret)}")
    if not ret.empty:
        print("\nRetention window (hari) by price category:")
        print(ret.groupby("price_category")["retention_days"].describe())
        print("\nSample:")
        print(ret[["name", "price_category", "retention_days", "review_count"]].head(10))
