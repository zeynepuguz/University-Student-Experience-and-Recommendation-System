import psycopg
from dotenv import load_dotenv
import os

load_dotenv()

# Tek parça bağlantı adresi (örn. Neon) varsa onu kullan; yoksa
# 5 ayrı POSTGRESQL_* değişkenine düş. Bu, tek bir doğru değeri
# yönetmeyi (host/port/db/user/password'u ayrı ayrı eşleştirmek
# yerine) kolaylaştırıyor.
DATABASE_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")


def get_connection():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL)

    return psycopg.connect(
        host=os.getenv("POSTGRESQL_HOST"),
        port=os.getenv("POSTGRESQL_PORT"),
        dbname=os.getenv("POSTGRESQL_DB"),
        user=os.getenv("POSTGRESQL_USER"),
        password=os.getenv("POSTGRESQL_PASSWORD")
    )