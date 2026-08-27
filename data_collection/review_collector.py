import os
import json

from database import get_connection
from data_collection.sources.youtube_collector import collect_youtube_reviews
from data_collection.sources.web_collector import collect_web_reviews
from data_collection.sources.sikayetvar_collector import collect_sikayetvar_reviews


def get_university_id(university_name):
    """
    Üniversite adına göre üniversite ID'sini getirir.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM universities
        WHERE name = %s
        """,
        (university_name,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]

    return None


def get_all_universities():
    """
    Veritabanındaki tüm üniversiteleri getirir.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, city, university_type, website
        FROM universities
        ORDER BY id
        """
    )

    universities = cursor.fetchall()

    cursor.close()
    conn.close()

    return universities


def review_exists(university_id, review_text):
    """
    Aynı üniversite için aynı yorum metninin
    daha önce kaydedilip kaydedilmediğini kontrol eder.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM reviews
        WHERE university_id = %s
          AND review_text = %s
        LIMIT 1
        """,
        (university_id, review_text)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result is not None


def add_review(
    university_id,
    review_text,
    source,
    review_date=None,
    source_url=None
):
    """
    Tek bir yorumu veritabanına kaydeder.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO reviews (
            university_id,
            review_text,
            source,
            review_date,
            source_url
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            university_id,
            review_text,
            source,
            review_date,
            source_url
        )
    )

    conn.commit()

    cursor.close()
    conn.close()


def save_reviews(university_name, reviews):
    """
    Bir üniversiteye ait birden fazla yorumu
    veritabanına kaydeder.
    """

    university_id = get_university_id(university_name)

    if not university_id:
        print(f"Üniversite bulunamadı: {university_name}")
        return

    print(
        f"\nÜniversite: {university_name} "
        f"| ID: {university_id}"
    )

    saved_count = 0
    skipped_count = 0

    for review in reviews:

        review_text = review.get("review_text")
        source = review.get("source")
        review_date = review.get("review_date")
        metadata = review.get("metadata", {})
        source_url = metadata.get("video_url") or metadata.get("topic_url")

        if not review_text:
            continue

        if review_exists(university_id, review_text):
            skipped_count += 1
            continue

        add_review(
            university_id=university_id,
            review_text=review_text,
            source=source,
            review_date=review_date,
            source_url=source_url
        )

        saved_count += 1

    print(
        f"✓ {saved_count} yorum başarıyla kaydedildi."
    )

    if skipped_count:
        print(
            f"↷ {skipped_count} yorum zaten kayıtlı "
            f"olduğu için atlandı."
        )


def university_has_reviews(university_id, source=None):
    """
    Üniversitenin veritabanında zaten en az bir yorumu
    olup olmadığını kontrol eder.

    `source` verilirse (örn. "youtube_comment", "eksisozluk"),
    kontrol sadece o kaynağa göre yapılır. Bu sayede bir
    üniversite bir kaynaktan toplanmış olsa bile diğer
    kaynaklardan toplama işlemi atlanmaz.
    """

    conn = get_connection()
    cursor = conn.cursor()

    if source:
        cursor.execute(
            """
            SELECT 1
            FROM reviews
            WHERE university_id = %s
              AND source = %s
            LIMIT 1
            """,
            (university_id, source)
        )
    else:
        cursor.execute(
            """
            SELECT 1
            FROM reviews
            WHERE university_id = %s
            LIMIT 1
            """,
            (university_id,)
        )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result is not None


def collect_youtube_reviews_for_all_universities(
    limit=10,
    max_videos=5,
    max_comments=30
):
    """
    Veritabanındaki üniversiteler için sırayla YouTube yorumu toplar.

    Zaten en az bir yorumu olan üniversiteler atlanır; bu hem kota
    israfını önler hem de fonksiyonu bölünerek tekrar tekrar
    çalıştırılabilir (resume) hale getirir.

    `limit`: YouTube API günlük kotası nedeniyle bu çalıştırmada
    işlenecek maksimum YENİ üniversite sayısı.
    """

    universities = get_all_universities()

    print("\n" + "=" * 60)
    print(f"TOPLU YOUTUBE TOPLAMA BAŞLIYOR (limit={limit})")
    print("=" * 60)

    processed_count = 0
    skipped_count = 0
    failed_universities = []

    for university in universities:

        if processed_count >= limit:
            print(f"\nLimit doldu ({limit}), durduruluyor.")
            break

        university_id = university[0]
        university_name = university[1]

        if university_has_reviews(university_id, source="youtube_comment"):
            skipped_count += 1
            continue

        try:

            collect_youtube_reviews_for_university(
                university_name=university_name,
                max_videos=max_videos,
                max_comments=max_comments
            )

            processed_count += 1

        except Exception as e:

            print(f"\n! Hata ({university_name}): {e}")

            failed_universities.append(university_name)

    print("\n" + "=" * 60)
    print("TOPLU TOPLAMA TAMAMLANDI")
    print(f"İşlenen (yeni): {processed_count}")
    print(f"Atlanan (zaten veri var): {skipped_count}")
    print(f"Başarısız: {len(failed_universities)}")

    if failed_universities:
        print(f"Başarısız Üniversiteler: {failed_universities}")

    print("=" * 60)


def export_reviews_for_rag(
    output_path="data_collection/exports/reviews.jsonl"
):
    """
    reviews tablosundaki, review_cleaner tarafından "işe yarar"
    (is_useful = TRUE) olarak işaretlenmiş yorumları, ileride
    embedding/RAG aşamasında kullanılabilecek LangChain Document
    formatına (page_content + metadata) uygun tek bir .jsonl
    dosyasına aktarır.

    is_useful henüz NULL (hiç sınıflandırılmamış) ya da FALSE
    (işe yaramaz) olan satırlar dışa aktarılmaz.
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

    os.makedirs(
        os.path.dirname(output_path),
        exist_ok=True
    )

    with open(output_path, "w", encoding="utf-8") as f:

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

            document = {
                "page_content": review_text,
                "metadata": {
                    "review_id": review_id,
                    "university_id": university_id,
                    "university_name": university_name,
                    "city": city,
                    "source": source,
                    "source_url": source_url,
                    "review_date": (
                        review_date.isoformat()
                        if review_date else None
                    )
                }
            }

            f.write(
                json.dumps(document, ensure_ascii=False) + "\n"
            )

    print(
        f"\n✓ {len(rows)} yorum "
        f"'{output_path}' dosyasına aktarıldı."
    )


def collect_youtube_reviews_for_university(
    university_name,
    max_videos=5,
    max_comments=30
):
    """
    Belirtilen üniversite için YouTube'da yorum toplar
    ve bulunan yorumları veritabanına kaydeder.
    """

    print("\n" + "=" * 60)
    print(f"YouTube yorumları toplanıyor: {university_name}")
    print("=" * 60)

    query = f"{university_name} öğrenci yorumları"

    reviews = collect_youtube_reviews(
        university_name=university_name,
        max_videos_per_query=max_videos,
        max_comments=max_comments
    )

    if not reviews:
        print("\nKaydedilecek yorum bulunamadı.")
        return

    print(
        f"\nToplam bulunan yorum: {len(reviews)}"
    )

    save_reviews(
        university_name=university_name,
        reviews=reviews
    )


def collect_web_reviews_for_university(
    university_name,
    max_pages=5
):
    """
    Belirtilen üniversite için Ekşi Sözlük'ten girdi toplar
    ve bulunan yorumları veritabanına kaydeder.
    """

    print("\n" + "=" * 60)
    print(f"Web yorumları toplanıyor: {university_name}")
    print("=" * 60)

    reviews = collect_web_reviews(
        university_name,
        max_pages=max_pages
    )

    if not reviews:
        print("\nKaydedilecek yorum bulunamadı.")
        return

    print(
        f"\nToplam bulunan yorum: {len(reviews)}"
    )

    save_reviews(
        university_name=university_name,
        reviews=reviews
    )


def collect_web_reviews_for_all_universities(
    limit=10,
    max_pages=5
):
    """
    Veritabanındaki üniversiteler için sırayla Ekşi Sözlük'ten
    yorum toplar.

    Zaten "eksisozluk" kaynağından yorumu olan üniversiteler
    atlanır; bu hem gereksiz isteği önler hem de fonksiyonu
    bölünerek tekrar tekrar çalıştırılabilir (resume) hale getirir.

    `limit`: bu çalıştırmada işlenecek maksimum YENİ üniversite
    sayısı.
    """

    universities = get_all_universities()

    print("\n" + "=" * 60)
    print(f"TOPLU WEB TOPLAMA BAŞLIYOR (limit={limit})")
    print("=" * 60)

    processed_count = 0
    skipped_count = 0
    failed_universities = []

    for university in universities:

        if processed_count >= limit:
            print(f"\nLimit doldu ({limit}), durduruluyor.")
            break

        university_id = university[0]
        university_name = university[1]

        if university_has_reviews(university_id, source="eksisozluk"):
            skipped_count += 1
            continue

        try:

            collect_web_reviews_for_university(
                university_name=university_name,
                max_pages=max_pages
            )

            processed_count += 1

        except Exception as e:

            print(f"\n! Hata ({university_name}): {e}")

            failed_universities.append(university_name)

    print("\n" + "=" * 60)
    print("TOPLU TOPLAMA TAMAMLANDI")
    print(f"İşlenen (yeni): {processed_count}")
    print(f"Atlanan (zaten veri var): {skipped_count}")
    print(f"Başarısız: {len(failed_universities)}")

    if failed_universities:
        print(f"Başarısız Üniversiteler: {failed_universities}")

    print("=" * 60)


def collect_sikayetvar_reviews_for_university(
    university_name,
    max_complaints=20
):
    """
    Belirtilen üniversite için ŞikayetVar'dan şikayet toplar
    ve bulunan yorumları veritabanına kaydeder.
    """

    print("\n" + "=" * 60)
    print(f"ŞikayetVar yorumları toplanıyor: {university_name}")
    print("=" * 60)

    reviews = collect_sikayetvar_reviews(
        university_name,
        max_complaints=max_complaints
    )

    if not reviews:
        print("\nKaydedilecek yorum bulunamadı.")
        return

    print(
        f"\nToplam bulunan yorum: {len(reviews)}"
    )

    save_reviews(
        university_name=university_name,
        reviews=reviews
    )


def collect_sikayetvar_reviews_for_all_universities(
    limit=10,
    max_complaints=20
):
    """
    Veritabanındaki üniversiteler için sırayla ŞikayetVar'dan
    şikayet toplar.

    Zaten "sikayetvar" kaynağından yorumu olan üniversiteler
    atlanır (resume mantığı).

    `limit`: bu çalıştırmada işlenecek maksimum YENİ üniversite
    sayısı.
    """

    universities = get_all_universities()

    print("\n" + "=" * 60)
    print(f"TOPLU ŞİKAYETVAR TOPLAMA BAŞLIYOR (limit={limit})")
    print("=" * 60)

    processed_count = 0
    skipped_count = 0
    failed_universities = []

    for university in universities:

        if processed_count >= limit:
            print(f"\nLimit doldu ({limit}), durduruluyor.")
            break

        university_id = university[0]
        university_name = university[1]

        if university_has_reviews(university_id, source="sikayetvar"):
            skipped_count += 1
            continue

        try:

            collect_sikayetvar_reviews_for_university(
                university_name=university_name,
                max_complaints=max_complaints
            )

            processed_count += 1

        except Exception as e:

            print(f"\n! Hata ({university_name}): {e}")

            failed_universities.append(university_name)

    print("\n" + "=" * 60)
    print("TOPLU TOPLAMA TAMAMLANDI")
    print(f"İşlenen (yeni): {processed_count}")
    print(f"Atlanan (zaten veri var): {skipped_count}")
    print(f"Başarısız: {len(failed_universities)}")

    if failed_universities:
        print(f"Başarısız Üniversiteler: {failed_universities}")

    print("=" * 60)


def show_all_universities():
    """
    Sistemdeki tüm üniversiteleri ekrana yazdırır.
    Test amaçlıdır.
    """

    universities = get_all_universities()

    print(
        f"\nToplam üniversite sayısı: "
        f"{len(universities)}\n"
    )

    for university in universities:

        university_id = university[0]
        university_name = university[1]
        city = university[2]
        university_type = university[3]

        print(
            f"ID: {university_id} | "
            f"{university_name} | "
            f"{city} | "
            f"{university_type}"
        )


if __name__ == "__main__":

    collect_web_reviews_for_all_universities(
        limit=10,
        max_pages=5
    )