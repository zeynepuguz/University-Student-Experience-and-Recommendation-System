from database import get_connection


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


def add_review(
    university_id,
    review_text,
    source,
    review_date=None
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
            review_date
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            university_id,
            review_text,
            source,
            review_date
        )
    )

    conn.commit()

    cursor.close()
    conn.close()


def save_reviews(university_name, reviews):
    """
    Bir üniversiteye ait birden fazla yorumu
    veritabanına kaydeder.

    reviews örneği:

    [
        {
            "review_text": "Kampüs güzel.",
            "source": "example",
            "review_date": None
        }
    ]
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

    for review in reviews:

        review_text = review.get("review_text")
        source = review.get("source")
        review_date = review.get("review_date")

        if not review_text:
            continue

        add_review(
            university_id=university_id,
            review_text=review_text,
            source=source,
            review_date=review_date
        )

        saved_count += 1

    print(
        f"✓ {saved_count} yorum başarıyla kaydedildi."
    )


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
    show_all_universities()