import pandas as pd
from sqlalchemy import create_engine
from pymongo import MongoClient

from db.config import MYSQL_URL, MONGO_URL, MONGO_DB

# Tag yang bukan genre — descriptor umum yang tidak informatif untuk analisis
NON_GENRE_TAGS = {
    "Indie", "Singleplayer", "Multiplayer", "Co-op", "Online Co-Op",
    "Local Co-Op", "Local Multiplayer", "Online Multiplayer",
    "Steam Achievements", "Steam Cloud", "Steam Trading Cards",
    "Full Controller Support", "Partial Controller Support",
    "Great Soundtrack", "Family Friendly",
}


def get_indie_genre_gap():
    """
    Q2: Indie Genre Gap — definisi indie = game yang di-tag 'Indie' oleh komunitas SteamSpy.

    Asumsi: game indie = game yang secara konsensus komunitas Steam diklasifikasikan
    sebagai indie melalui SteamSpy community tagging.

    Alur:
    1. MongoDB Steams_Tags_Genre: ambil semua appid yang ber-tag 'Indie'
    2. MySQL: filter 2016-2021 + ambil sentiment (positive/negative ratings)
    3. MongoDB lagi: ambil genre tags lain (selain 'Indie') per game
    4. Group by genre tag → hitung volume dan avg positive ratio

    Returns DataFrame: tag, game_count, avg_positive_ratio
    """
    # Step 1: appid yang ber-tag Indie dari MongoDB
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]

    indie_docs = list(
        db["Steams_Tags_Genre"].find(
            {"tags": "Indie"},
            {"appid": 1, "tags": 1, "_id": 0},
        )
    )
    client.close()

    if not indie_docs:
        return pd.DataFrame(columns=["tag", "game_count", "avg_positive_ratio"])

    indie_appids = [d["appid"] for d in indie_docs]

    # Step 2: MySQL — filter 2016-2021, ambil sentiment
    engine = create_engine(MYSQL_URL)
    placeholders = ",".join(str(a) for a in indie_appids)
    df_mysql = pd.read_sql(
        f"SELECT appid, positive_ratings, negative_ratings "
        f"FROM clean_mysql_katalog "
        f"WHERE release_date >= '2016-01-01' "
        f"AND positive_ratings + negative_ratings > 0 "
        f"AND appid IN ({placeholders})",
        engine,
    )
    engine.dispose()

    df_mysql["positive_ratio"] = (
        df_mysql["positive_ratings"] / (df_mysql["positive_ratings"] + df_mysql["negative_ratings"])
    )
    valid_appids = set(df_mysql["appid"].tolist())

    # Step 3: tags lain per game (exclude Indie dan non-genre tags)
    tags_map = pd.DataFrame(indie_docs)
    tags_map = tags_map[tags_map["appid"].isin(valid_appids)]

    def other_tags(tag_list):
        if not isinstance(tag_list, list):
            return []
        return [t for t in tag_list if t not in NON_GENRE_TAGS]

    tags_map["genre_tags"] = tags_map["tags"].apply(other_tags)

    exploded = (
        tags_map[["appid", "genre_tags"]]
        .explode("genre_tags")
        .rename(columns={"genre_tags": "tag"})
        .dropna(subset=["tag"])
    )
    exploded = exploded[exploded["tag"] != ""]

    # Step 4: merge sentiment, group by tag
    merged = pd.merge(exploded, df_mysql[["appid", "positive_ratio"]], on="appid", how="inner")

    result = (
        merged.groupby("tag")
        .agg(
            game_count=("appid", "nunique"),
            avg_positive_ratio=("positive_ratio", "mean"),
        )
        .reset_index()
    )
    result = (
        result[result["game_count"] >= 3]
        .sort_values("game_count", ascending=False)
        .reset_index(drop=True)
    )
    return result


if __name__ == "__main__":
    df = get_indie_genre_gap()
    print(f"{len(df)} genre tags found")
    print(df.head(20).to_string())
