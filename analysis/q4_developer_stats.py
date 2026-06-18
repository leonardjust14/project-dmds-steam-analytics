import pandas as pd
from sqlalchemy import create_engine

from db.config import MYSQL_URL

MIN_GAMES_THRESHOLD = 3


def build_developer_stats_table():
    engine = create_engine(MYSQL_URL)

    df = pd.read_sql(
        "SELECT developer, price, positive_ratings, negative_ratings "
        "FROM clean_mysql_katalog "
        "WHERE positive_ratings + negative_ratings > 0",
        engine,
    )

    df["total_ratings"] = df["positive_ratings"] + df["negative_ratings"]
    df["positive_ratio"] = df["positive_ratings"] / df["total_ratings"]

    stats = (
        df.groupby("developer")
        .agg(
            game_count=("developer", "count"),
            avg_price=("price", "mean"),
            avg_positive_ratio=("positive_ratio", "mean"),
            total_reviews=("total_ratings", "sum"),
        )
        .reset_index()
    )

    stats = stats[stats["game_count"] >= MIN_GAMES_THRESHOLD].copy()
    stats = stats.sort_values("game_count", ascending=False).reset_index(drop=True)

    stats.to_sql("developer_stats", engine, if_exists="replace", index=False)
    engine.dispose()

    print(f"developer_stats created: {len(stats)} developers (>= {MIN_GAMES_THRESHOLD} games)")
    return stats


def get_developer_stats():
    engine = create_engine(MYSQL_URL)
    df = pd.read_sql("SELECT * FROM developer_stats", engine)
    engine.dispose()
    return df


if __name__ == "__main__":
    df = build_developer_stats_table()
    print("\nTop 5 by volume:")
    print(df.nlargest(5, "game_count")[["developer", "game_count", "avg_positive_ratio"]])
    print("\nTop 5 by rating (min 3 games):")
    print(df.nlargest(5, "avg_positive_ratio")[["developer", "game_count", "avg_positive_ratio"]])
