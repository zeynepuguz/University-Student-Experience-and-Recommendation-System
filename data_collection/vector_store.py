import os
import json

import chromadb
from openai import OpenAI
from dotenv import load_dotenv

from database import get_connection


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"

CHROMA_PATH = "data_collection/chroma_db"
COLLECTION_NAME = "university_reviews"


def get_collection():
    """
    Kalıcı (disk üzerinde saklanan) Chroma koleksiyonunu getirir,
    yoksa oluşturur.
    """

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    return chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def load_documents(input_path="data_collection/exports/reviews.jsonl"):
    """
    export_reviews_for_rag() tarafından üretilen .jsonl dosyasını okur.
    """

    documents = []

    with open(input_path, encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            documents.append(json.loads(line))

    return documents


def load_documents_from_db():
    """
    "İşe yarar" (is_useful = TRUE) yorumları doğrudan veritabanından
    okur; export_reviews_for_rag()'in ürettiği .jsonl dosyasıyla aynı
    doküman formatını üretir. Dosyaya bağımlı olmadığı için, kalıcı
    disk olmayan ortamlarda (örn. ücretsiz hosting) vector store'u
    sıfırdan kurmak için kullanılır.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            r.id,
            r.review_text,
            r.source,
            r.review_date,
            r.source_url,
            u.id,
            u.name,
            u.city
        FROM reviews r
        JOIN universities u ON u.id = r.university_id
        WHERE r.is_useful = TRUE
        ORDER BY u.id, r.id
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    documents = []

    for row in rows:

        (
            review_id,
            review_text,
            source,
            review_date,
            source_url,
            university_id,
            university_name,
            city
        ) = row

        documents.append({
            "page_content": review_text,
            "metadata": {
                "review_id": review_id,
                "university_id": university_id,
                "university_name": university_name,
                "city": city,
                "source": source,
                "source_url": source_url,
                "review_date": (
                    review_date.isoformat() if review_date else None
                )
            }
        })

    return documents


def embed_texts(texts):
    """
    Bir metin listesini tek bir API çağrısında embedding'e çevirir.
    """

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    return [item.embedding for item in response.data]


def add_documents_to_collection(documents, collection, batch_size=100):
    """
    Doküman listesini embed edip verilen Chroma koleksiyonuna ekler.

    Zaten koleksiyonda bulunan review_id'ler atlanır (resume mantığı),
    bu sayede fonksiyon tekrar tekrar çalıştırılabilir.
    """

    print("\n" + "=" * 60)
    print(f"VECTOR STORE OLUŞTURULUYOR — Toplam doküman: {len(documents)}")
    print("=" * 60)

    added_count = 0
    skipped_count = 0

    for start in range(0, len(documents), batch_size):

        batch = documents[start:start + batch_size]

        ids = [
            f"review_{doc['metadata']['review_id']}"
            for doc in batch
        ]

        existing_ids = set(collection.get(ids=ids)["ids"])

        new_batch = [
            (doc, doc_id)
            for doc, doc_id in zip(batch, ids)
            if doc_id not in existing_ids
        ]

        skipped_count += len(batch) - len(new_batch)

        if not new_batch:
            continue

        texts = [doc["page_content"] for doc, _ in new_batch]
        new_ids = [doc_id for _, doc_id in new_batch]

        # Chroma metadata'da None değer kabul etmiyor, temizle
        metadatas = []

        for doc, _ in new_batch:

            cleaned = {
                key: value
                for key, value in doc["metadata"].items()
                if value is not None
            }

            metadatas.append(cleaned)

        try:
            embeddings = embed_texts(texts)
        except Exception as e:
            print(
                f"! Hata (grup {start + 1}-{start + len(batch)}): {e}"
            )
            continue

        collection.add(
            ids=new_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        added_count += len(new_ids)

        print(
            f"Grup {start + 1}-{start + len(batch)} / {len(documents)} "
            f"| eklenen: {len(new_ids)} "
            f"| atlanan: {len(batch) - len(new_batch)}"
        )

    print("\n" + "=" * 60)
    print("VECTOR STORE TAMAMLANDI")
    print(f"Eklenen: {added_count}")
    print(f"Atlanan (zaten vardı): {skipped_count}")
    print(f"Koleksiyondaki toplam doküman: {collection.count()}")
    print("=" * 60)


def build_vector_store(
    input_path="data_collection/exports/reviews.jsonl",
    batch_size=100
):
    """
    .jsonl dosyasındaki dokümanları embed edip Chroma'ya kaydeder.
    (Yerel/manuel kullanım için — export dosyasına ihtiyaç duyar.)
    """

    documents = load_documents(input_path)
    collection = get_collection()

    add_documents_to_collection(documents, collection, batch_size)


def build_vector_store_from_db(batch_size=100):
    """
    "İşe yarar" yorumları doğrudan veritabanından okuyup Chroma'ya
    kaydeder. Dosyaya ihtiyaç duymaz; kalıcı disk sağlamayan
    ortamlarda (örn. ücretsiz hosting) başlangıçta vector store'u
    sıfırdan kurmak için kullanılır.
    """

    documents = load_documents_from_db()
    collection = get_collection()

    add_documents_to_collection(documents, collection, batch_size)


def ensure_vector_store_ready():
    """
    Koleksiyon boşsa (örn. kalıcı disk olmayan bir ortamda taze bir
    başlangıç yapıldıysa) veritabanından yeniden kurar. Doluysa
    hiçbir şey yapmaz. FastAPI başlangıcında çağrılmak için tasarlandı.
    """

    collection = get_collection()

    if collection.count() > 0:
        print(
            f"Vector store zaten dolu "
            f"({collection.count()} doküman), yeniden kurulmuyor."
        )
        return

    print("Vector store boş, veritabanından yeniden kuruluyor...")

    build_vector_store_from_db()


def query_vector_store(query_text, university_name=None, n_results=5):
    """
    Bir soru metnine göre koleksiyondaki en alakalı yorumları getirir.
    `university_name` verilirse sonuçlar o üniversiteyle sınırlanır.
    """

    collection = get_collection()

    query_embedding = embed_texts([query_text])[0]

    where = (
        {"university_name": university_name}
        if university_name else None
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where
    )

    return results


if __name__ == "__main__":
    build_vector_store()
