import pandas as pd
from sqlalchemy import create_engine

from config import MYSQL_URL

def get_mysql_data():
    engine = create_engine(MYSQL_URL)
    df = pd.read_sql(
        "SELECT appid, name, price, release_date, developer, publisher FROM clean_mysql_katalog",
        engine
    )
    engine.dispose()
    return df

if __name__ == "__main__":
    df = get_mysql_data()
    print(f"MySQL OK — {len(df)} rows")
    print(df.head())