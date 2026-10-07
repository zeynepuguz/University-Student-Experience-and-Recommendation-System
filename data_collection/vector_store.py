"""
Yorum embedding'leri ve benzerlik araması (Postgres + pgvector).

Embedding'ler eskiden backend sürecinin içindeki ChromaDB'de
tutuluyordu. Render'ın ücretsiz katmanında kalıcı disk olmadığı için
koleksiyon her açılışta boş başlıyor ve ~22.800 yorum baştan embed
ediliyordu (açılış başına ~2,7 milyon token). Üstüne bu embedding'ler
512 MB belleği aşınca servis çöküp yeniden başlıyor, yeniden kurulum
da baştan başlıyordu: kimse siteyi kullanmasa bile OpenAI faturası
işliyordu.

Artık embedding'ler Neon'daki `review_embeddings` tablosunda kalıcı
olarak duruyor; arama veritabanında yapılıyor, backend belleğine hiç
yüklenmiyor. Açılışta sadece embedding'i olmayan (yeni eklenmiş)
yorumlar embed ediliyor.
"""

import os
import time

from openai import OpenAI
from dotenv import load_dotenv

import usage_tracking
from database import get_connection


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# halfvec: her boyut 2 bayt (vector'ün yarısı). Arama kalitesine etkisi
# ihmal edilebilir; tablo ~140 MB yerine ~70 MB tutuyor (Neon'un
# ücretsiz katmanında depolama sınırlı).
CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS review_embeddings (
    review_id INTEGER PRIMARY KEY REFERENCES reviews(id) ON DELETE CASCADE,
    embedding halfvec({EMBEDDING_DIMENSIONS}) NOT NULL
)
"""


def ensure_table():
    """pgvector eklentisini ve embedding tablosunu yoksa oluşturur."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.execute(CREATE_TABLE)

    conn.commit()

    cursor.close()
    conn.close()


def to_pgvector(embedding):
    """
    Float listesini pgvector'ün metin biçimine ('[0.1,0.2,...]') çevirir.

    halfvec zaten ~4 anlamlı basamak tutuyor; 5 basamağa yuvarlamak
    hassasiyet kaybettirmeden gönderilen metni ~3 kat kısaltıyor
    (toplu taşımada fark ediyor).
    """

    return "[" + ",".join(f"{value:.5g}" for value in embedding) + "]"


def embed_texts(texts, feature="index_embedding"):
    """
    Bir metin listesini tek bir API çağrısında embedding'e çevirir.
    `feature`, kullanım kaydında çağrının nereden geldiğini belirtir.
    """

    started_at = time.monotonic()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    usage_tracking.record(feature, EMBEDDING_MODEL, response, started_at)

    return [item.embedding for item in response.data]


def store_embeddings(rows):
    """
    [(review_id, embedding), ...] listesini tabloya yazar. Zaten
    embedding'i olan yorumlar atlanır, böylece işlem tekrar tekrar
    çalıştırılabilir.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany(
        """
        INSERT INTO review_embeddings (review_id, embedding)
        VALUES (%s, %s::halfvec)
        ON CONFLICT (review_id) DO NOTHING
        """,
        [
            (review_id, to_pgvector(embedding))
            for review_id, embedding in rows
        ]
    )

    conn.commit()

    cursor.close()
    conn.close()


def load_reviews_without_embedding():
    """Embedding'i henüz olmayan "işe yarar" yorumları getirir."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.id, r.review_text
        FROM reviews r
        LEFT JOIN review_embeddings e ON e.review_id = r.id
        WHERE r.is_useful = TRUE
          AND e.review_id IS NULL
        ORDER BY r.id
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def build_vector_store(batch_size=100):
    """
    Embedding'i eksik olan yorumları embed edip tabloya yazar. Yeni
    yorum yoksa OpenAI'a hiç gidilmez.
    """

    ensure_table()

    reviews = load_reviews_without_embedding()

    print(f"Embedding'i eksik yorum: {len(reviews)}")

    added_count = 0

    for start in range(0, len(reviews), batch_size):

        batch = reviews[start:start + batch_size]

        try:
            embeddings = embed_texts([text for _, text in batch])
        except Exception as e:
            print(
                f"! Hata (grup {start + 1}-{start + len(batch)}): {e}"
            )
            continue

        store_embeddings(
            [
                (review_id, embedding)
                for (review_id, _), embedding in zip(batch, embeddings)
            ]
        )

        added_count += len(batch)

        print(
            f"Grup {start + 1}-{start + len(batch)} / {len(reviews)} "
            f"| eklenen: {len(batch)}"
        )

    print(f"Vector store güncel (eklenen: {added_count}).")


def ensure_vector_store_ready():
    """
    FastAPI başlangıcında çağrılır: veritabanına sonradan eklenen
    yorumların embedding'lerini tamamlar. Mevcut embedding'ler kalıcı
    olduğu için normalde hiçbir şey embed edilmez.
    """

    build_vector_store()


def query_vector_store(query_text, university_name=None, n_results=5):
    """
    Bir soru metnine göre en alakalı yorumları getirir.
    `university_name` verilirse sonuçlar o üniversiteyle sınırlanır.

    Dönüş biçimi Chroma'nınkiyle aynı ({"documents": [[...]],
    "metadatas": [[...]]}), rag.py bu biçime göre yazılmış.
    """

    query_embedding = embed_texts(
        [query_text],
        feature="query_embedding"
    )[0]

    university_filter = "AND u.name = %s" if university_name else ""

    params = [university_name] if university_name else []
    params += [to_pgvector(query_embedding), n_results]

    conn = get_connection()
    cursor = conn.cursor()

    # OpenAI embedding'leri birim uzunlukta; kosinüs mesafesi (<=>)
    # Chroma'nın kullandığı L2 ile aynı sıralamayı verir.
    cursor.execute(
        f"""
        SELECT
            r.review_text,
            r.id,
            u.id,
            u.name,
            u.city,
            r.source,
            r.source_url,
            r.review_date
        FROM review_embeddings e
        JOIN reviews r ON r.id = e.review_id
        JOIN universities u ON u.id = r.university_id
        WHERE r.is_useful = TRUE
          {university_filter}
        ORDER BY e.embedding <=> %s::halfvec
        LIMIT %s
        """,
        params
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    documents = []
    metadatas = []

    for (
        review_text,
        review_id,
        university_id,
        name,
        city,
        source,
        source_url,
        review_date
    ) in rows:

        documents.append(review_text)
        metadatas.append({
            "review_id": review_id,
            "university_id": university_id,
            "university_name": name,
            "city": city,
            "source": source,
            "source_url": source_url,
            "review_date": (
                review_date.isoformat() if review_date else None
            )
        })

    return {"documents": [documents], "metadatas": [metadatas]}


if __name__ == "__main__":
    build_vector_store()
