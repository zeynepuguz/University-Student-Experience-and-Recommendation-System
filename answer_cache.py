"""
Üretilen cevapların önbelleği.

/ask ve /compare her çağrıda OpenAI ücreti doğuruyor ve aynı soru
farklı ziyaretçilerden defalarca geliyor ("X üniversitesi nasıl",
"yurtlar nasıl" gibi). Aynı soru + aynı üniversite(ler) için üretilmiş
bir cevap varsa modele hiç gidilmiyor.

Yorum havuzu sürekli büyüdüğü için cevaplar zamanla eskiyor; bu yüzden
kayıtların TTL_DAYS'ten eski olanları yok sayılıyor.
"""

import hashlib
import os

from database import get_connection


TTL_DAYS = int(os.getenv("ANSWER_CACHE_TTL_DAYS", "30"))

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS answer_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) NOT NULL UNIQUE,
    question TEXT NOT NULL,
    universities TEXT,
    answer TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_table():
    """Önbellek tablosunu yoksa oluşturur (uygulama açılışında çağrılır)."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE)

    conn.commit()

    cursor.close()
    conn.close()


def build_key(question, universities):
    """
    Soru + üniversite(ler) için önbellek anahtarı üretir.

    Soru normalize ediliyor (küçük harf, baştaki/sondaki ve tekrar eden
    boşluklar atılıyor) ki aynı sorunun ufak yazım farkları ayrı kayıt
    açmasın. Karşılaştırmada üniversite sırası önemli olmadığı için
    liste sıralanıyor.
    """

    normalized_question = " ".join(question.lower().split())

    normalized_universities = ",".join(
        sorted(
            name.lower().strip()
            for name in universities
            if name
        )
    )

    raw = f"{normalized_question}|{normalized_universities}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_answer(cache_key):
    """
    Önbellekteki (ve henüz eskimemiş) cevabı döndürür, yoksa None.

    Okuma sırasında hit_count artırılıyor; hangi soruların gerçekten
    tekrarlandığını görmek için.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE answer_cache
        SET hit_count = hit_count + 1
        WHERE cache_key = %s
          AND created_at > CURRENT_TIMESTAMP - make_interval(days => %s)
        RETURNING answer
        """,
        (cache_key, TTL_DAYS)
    )

    row = cursor.fetchone()

    conn.commit()

    cursor.close()
    conn.close()

    return row[0] if row else None


def store_answer(cache_key, question, universities, answer):
    """Üretilen cevabı önbelleğe yazar; eskimiş kayıt varsa tazeler."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO answer_cache (cache_key, question, universities, answer)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (cache_key) DO UPDATE
        SET answer = EXCLUDED.answer,
            created_at = CURRENT_TIMESTAMP,
            hit_count = 0
        """,
        (
            cache_key,
            question,
            ",".join(name for name in universities if name),
            answer
        )
    )

    conn.commit()

    cursor.close()
    conn.close()
