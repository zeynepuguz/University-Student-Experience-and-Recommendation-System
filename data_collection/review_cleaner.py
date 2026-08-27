import os
import json

from openai import OpenAI
from dotenv import load_dotenv

from database import get_connection


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = """
Sen bir üniversite tercih asistanı için ham yorum verisini temizleyen
bir sınıflandırıcısın.

Sana YouTube yorumları ve Ekşi Sözlük girdilerinden oluşan bir liste
verilecek. Her yorum için, bu yorumun gerçek bir öğrenci deneyimi
paylaşım sistemi için (kampüs hayatı, eğitim kalitesi, sosyal imkanlar,
ulaşım, yurt, hocalar, şehir/yaşam maliyeti, staj imkanları, bölüm
tercihi gibi konularda) İŞE YARAR olup olmadığına karar ver.

İŞE YARAR (is_useful: true) sayılır:
- Üniversite hakkında gerçek bir deneyim, gözlem veya bilgi içeren yorumlar
- Üniversiteyle ilgili anlamlı bir soru (örn. "yurt uzak mı", "staj imkanı nasıl")
- Olumlu ya da olumsuz somut değerlendirmeler

İŞE YARAMAZ (is_useful: false) sayılır:
- Spam, reklam, kanal tanıtımı
- Doğum günü/tebrik/özlem gibi kişisel, üniversiteyle ilgisiz mesajlar
- Sadece emoji veya anlamsız kısa ifadeler
- Başka bir üniversite veya tamamen alakasız bir konu hakkında olan yorumlar
- İçeriksiz, hiçbir bilgi taşımayan tek kelimelik tepkiler

Her yorum için verilen "id" değerini birebir koru. Sonucu, verilen
şemaya uygun bir JSON olarak döndür. Listedeki her öğe için tam olarak
bir sonuç üret; hiçbir öğeyi atlama.
""".strip()

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "is_useful": {"type": "boolean"}
                },
                "required": ["id", "is_useful"],
                "additionalProperties": False
            }
        }
    },
    "required": ["results"],
    "additionalProperties": False
}


def get_unclassified_reviews(limit=None):
    """
    Henüz is_useful değeri belirlenmemiş (NULL) yorumları getirir.
    """

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, review_text
        FROM reviews
        WHERE is_useful IS NULL
        ORDER BY id
    """

    if limit:
        query += " LIMIT %s"
        cursor.execute(query, (limit,))
    else:
        cursor.execute(query)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


def update_is_useful(results):
    """
    Sınıflandırma sonuçlarını (id -> is_useful) veritabanına yazar.
    """

    conn = get_connection()
    cursor = conn.cursor()

    for review_id, is_useful in results:
        cursor.execute(
            """
            UPDATE reviews
            SET is_useful = %s
            WHERE id = %s
            """,
            (is_useful, review_id)
        )

    conn.commit()

    cursor.close()
    conn.close()


def classify_batch(reviews):
    """
    Bir grup yorumu ("id" ve "review_text" içeren tuple listesi)
    modele gönderip her biri için is_useful kararı alır.

    Dönüş: [(id, is_useful), ...]
    """

    items = [
        {"id": review_id, "review_text": review_text}
        for review_id, review_text in reviews
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(items, ensure_ascii=False)
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "review_classification",
                "schema": RESPONSE_SCHEMA,
                "strict": True
            }
        }
    )

    content = response.choices[0].message.content

    parsed = json.loads(content)

    results = [
        (item["id"], item["is_useful"])
        for item in parsed["results"]
    ]

    # Modelin atladığı id varsa (olmaması gerekir ama garanti
    # olsun diye) bunları güvenli tarafta tutup "işe yarar" say.
    returned_ids = {review_id for review_id, _ in results}

    for review_id, _ in reviews:
        if review_id not in returned_ids:
            results.append((review_id, True))

    return results


def clean_all_reviews(batch_size=40, limit=None):
    """
    Veritabanındaki sınıflandırılmamış tüm yorumları gruplar
    halinde modele gönderip is_useful alanını doldurur.
    """

    reviews = get_unclassified_reviews(limit=limit)

    print("\n" + "=" * 60)
    print(f"TEMİZLİK BAŞLIYOR — Sınıflandırılacak yorum: {len(reviews)}")
    print("=" * 60)

    total_useful = 0
    total_not_useful = 0
    batch_count = 0

    for start in range(0, len(reviews), batch_size):

        batch = reviews[start:start + batch_size]

        batch_count += 1

        print(
            f"\nGrup {batch_count} işleniyor "
            f"({start + 1}-{start + len(batch)} / {len(reviews)})"
        )

        try:
            results = classify_batch(batch)
        except Exception as e:
            print(f"! Hata (grup {batch_count}): {e}")
            continue

        update_is_useful(results)

        useful_count = sum(1 for _, is_useful in results if is_useful)
        not_useful_count = len(results) - useful_count

        total_useful += useful_count
        total_not_useful += not_useful_count

        print(
            f"  ✓ işe yarar: {useful_count} "
            f"| ✗ işe yaramaz: {not_useful_count}"
        )

    print("\n" + "=" * 60)
    print("TEMİZLİK TAMAMLANDI")
    print(f"Toplam işe yarar: {total_useful}")
    print(f"Toplam işe yaramaz: {total_not_useful}")
    print("=" * 60)


if __name__ == "__main__":
    clean_all_reviews(batch_size=40)
