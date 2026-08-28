"""
Yerel PostgreSQL'deki universities ve reviews tablolarını Neon'a
(ya da .env'de NEON_DATABASE_URL ile belirtilen herhangi bir hedef
PostgreSQL'e) taşır.

Kullanım:
    1. .env dosyasına şu satırı ekle:
       NEON_DATABASE_URL=postgresql://kullanici:sifre@host/db?sslmode=require
    2. python -m data_collection.migrate_to_neon
"""

import os

import psycopg
from dotenv import load_dotenv

from database import get_connection


load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")

CREATE_UNIVERSITIES = """
CREATE TABLE IF NOT EXISTS universities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    city VARCHAR(100),
    university_type VARCHAR(50),
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_REVIEWS = """
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    review_text TEXT NOT NULL,
    source VARCHAR(100),
    review_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_url TEXT,
    is_useful BOOLEAN
)
"""


def migrate():

    if not NEON_DATABASE_URL:
        print(
            "NEON_DATABASE_URL .env dosyasında bulunamadı. "
            "Önce ekleyip tekrar dene."
        )
        return

    local_conn = get_connection()
    local_cur = local_conn.cursor()

    neon_conn = psycopg.connect(NEON_DATABASE_URL)
    neon_cur = neon_conn.cursor()

    print("Şema oluşturuluyor...")

    neon_cur.execute(CREATE_UNIVERSITIES)
    neon_cur.execute(CREATE_REVIEWS)
    neon_conn.commit()

    print("universities taşınıyor...")

    local_cur.execute(
        """
        SELECT id, name, city, university_type, website, created_at
        FROM universities
        ORDER BY id
        """
    )

    universities = local_cur.fetchall()

    for row in universities:

        neon_cur.execute(
            """
            INSERT INTO universities (
                id, name, city, university_type, website, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            row
        )

    neon_conn.commit()

    print(f"  {len(universities)} üniversite taşındı.")

    print("reviews taşınıyor (bu biraz sürebilir)...")

    local_cur.execute(
        """
        SELECT
            id, university_id, review_text, source, review_date,
            created_at, source_url, is_useful
        FROM reviews
        ORDER BY id
        """
    )

    reviews = local_cur.fetchall()

    batch_size = 500

    for start in range(0, len(reviews), batch_size):

        batch = reviews[start:start + batch_size]

        neon_cur.executemany(
            """
            INSERT INTO reviews (
                id, university_id, review_text, source, review_date,
                created_at, source_url, is_useful
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            batch
        )

        neon_conn.commit()

        print(f"  {start + len(batch)} / {len(reviews)}")

    print(f"  {len(reviews)} yorum taşındı.")

    print("Sequence'lar (otomatik id sayaçları) düzeltiliyor...")

    neon_cur.execute(
        "SELECT setval('universities_id_seq', "
        "(SELECT COALESCE(MAX(id), 1) FROM universities))"
    )
    neon_cur.execute(
        "SELECT setval('reviews_id_seq', "
        "(SELECT COALESCE(MAX(id), 1) FROM reviews))"
    )
    neon_conn.commit()

    # Doğrulama
    neon_cur.execute("SELECT COUNT(*) FROM universities")
    uni_count = neon_cur.fetchone()[0]

    neon_cur.execute("SELECT COUNT(*) FROM reviews")
    review_count = neon_cur.fetchone()[0]

    print("\n" + "=" * 50)
    print("TAŞIMA TAMAMLANDI")
    print(f"Neon'daki üniversite sayısı: {uni_count}")
    print(f"Neon'daki yorum sayısı: {review_count}")
    print("=" * 50)

    local_cur.close()
    local_conn.close()
    neon_cur.close()
    neon_conn.close()


if __name__ == "__main__":
    migrate()
