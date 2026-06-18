import pandas as pd
from sqlalchemy import create_engine

from db.config import MYSQL_URL

BUCKET_ORDER = ["Free", "$0-5", "$5-15", "$15-30", "$30+"]


def _price_bucket(price):
    if price == 0:
        return "Free"
    elif price <= 5:
        return "$0-5"
    elif price <= 15:
        return "$5-15"
    elif price <= 30:
        return "$15-30"
    else:
        return "$30+"


def get_price_sentiment():
    """
    Q1: Harga vs Sentimen — pakai positive_ratings & negative_ratings dari MySQL.
    Mencakup semua 27K game, bukan sampling.
    Returns DataFrame: price_bucket, game_count, avg_positive_ratio, total_reviews
    """
    engine = create_engine(MYSQL_URL)
    df = pd.read_sql(
        "SELECT appid, price, positive_ratings, negative_ratings "
        "FROM clean_mysql_katalog "
        "WHERE positive_ratings + negative_ratings > 0",
        engine,
    )
    engine.dispose()

    df["total_ratings"] = df["positive_ratings"] + df["negative_ratings"]
    df["positive_ratio"] = df["positive_ratings"] / df["total_ratings"]
    df["price_bucket"] = df["price"].apply(_price_bucket)

    result = (
        df.groupby("price_bucket")
        .agg(
            game_count=("appid", "count"),
            avg_positive_ratio=("positive_ratio", "mean"),
            total_reviews=("total_ratings", "sum"),
        )
        .reset_index()
    )
    result["price_bucket"] = pd.Categorical(
        result["price_bucket"], categories=BUCKET_ORDER, ordered=True
    )
    result = result.sort_values("price_bucket").reset_index(drop=True)
    return result


if __name__ == "__main__":
    df = get_price_sentiment()
    print(df.to_string())
