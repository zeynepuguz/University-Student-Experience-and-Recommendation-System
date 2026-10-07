"""
Yerel ChromaDB'deki embedding'leri Neon'daki `review_embeddings`
tablosuna kopyalar (tek seferlik).

Embedding'ler zaten hesaplanmış olduğu için OpenAI'a hiç gidilmez.
Tekrar çalıştırılabilir: tabloda olan yorumlar atlanır. Chroma'da
olmayan yorumlar için backend açılışta (ya da
`python -m data_collection.vector_store`) eksikleri embed eder.

chromadb artık requirements.txt'te değil; bu betik yalnızca
chromadb'nin kurulu olduğu yerel ortamda çalıştırılır:

    python -m data_collection.migrate_chroma_to_pgvector
"""

import chromadb

from data_collection.console import force_utf8_output
from data_collection.vector_store import ensure_table, store_embeddings
from database import get_connection


CHROMA_PATH = "data_collection/chroma_db"
COLLECTION_NAME = "university_reviews"


def load_pending_review_ids():
    """Hem `reviews`'da olan hem de embedding'i henüz yazılmamış id'ler."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.id
        FROM reviews r
        LEFT JOIN review_embeddings e ON e.review_id = r.id
        WHERE e.review_id IS NULL
        """
    )

    ids = {row[0] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return ids


def migrate(batch_size=500):

    ensure_table()

    pending_ids = load_pending_review_ids()

    collection = chromadb.PersistentClient(
        path=CHROMA_PATH
    ).get_collection(COLLECTION_NAME)

    total = collection.count()

    print(f"Chroma'da {total} doküman var, kopyalanıyor...")

    copied = 0

    for offset in range(0, total, batch_size):

        batch = collection.get(
            offset=offset,
            limit=batch_size,
            include=["embeddings"]
        )

        rows = []

        for doc_id, embedding in zip(batch["ids"], batch["embeddings"]):

            review_id = int(doc_id.removeprefix("review_"))

            # Veritabanında olmayan (silinmiş) ya da zaten kopyalanmış
            # yorumlar atlanıyor; aksi halde foreign key hata verir.
            if review_id in pending_ids:
                rows.append((review_id, list(embedding)))

        if rows:
            store_embeddings(rows)

        copied += len(rows)

        print(
            f"{min(offset + batch_size, total)} / {total} "
            f"| kopyalanan: {copied}"
        )

    print(f"\nTamamlandı. Kopyalanan: {copied}")


if __name__ == "__main__":
    force_utf8_output()

    migrate()
