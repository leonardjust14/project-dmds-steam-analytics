import os

from dotenv import load_dotenv

load_dotenv()

MYSQL_ROOT_PASSWORD = os.environ["MYSQL_ROOT_PASSWORD"]
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3307")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "steam_katalog")
MYSQL_URL = f"mysql+pymysql://root:{MYSQL_ROOT_PASSWORD}@localhost:{MYSQL_PORT}/{MYSQL_DATABASE}"

MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_URL = f"mongodb://localhost:{MONGO_PORT}/"
MONGO_DB = os.environ.get("MONGO_DB", "Steams_Analytics")
