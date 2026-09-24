"""
Frontend'in build'e gömdüğü anlık görüntüleri üretir.

İki dosya yazar:

- universities.json — açılır listedeki üniversiteler. Bu liste pratikte
  sabit bir veri ama backend'den çekiliyordu; Render'ın ücretsiz katmanı
  backend'i uykuya aldığı için istek 1-3 dakika sürebiliyor ve o süre
  boyunca liste boş kalıyordu. Gömülü olunca backend'in durumundan
  bağımsız olarak anında dolu geliyor.

- stats.json — "Bu nasıl çalışıyor?" bölümündeki veri sayıları. Elle
  yazılsa her toplamadan sonra eskiyeceği için veritabanından üretiliyor.

Veri değiştikten sonra tekrar çalıştır:
    python -m data_collection.export_frontend_data
"""

import json
import os
from datetime import date

from database import get_connection


UNIVERSITIES_PATH = "frontend/src/universities.json"
STATS_PATH = "frontend/src/stats.json"

# Kaynak anahtarlarının okunur karşılıkları.
SOURCE_LABELS = {
    "eksisozluk": "Ekşi Sözlük",
    "uludagsozluk": "Uludağ Sözlük",
    "youtube_comment": "YouTube",
    "sikayetvar": "ŞikayetVar",
}


def export_universities(output_path=UNIVERSITIES_PATH):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, city, university_type
        FROM universities
        ORDER BY name
        """
    )

    universities = [
        {
            "id": row[0],
            "name": row[1],
            "city": row[2],
            "university_type": row[3]
        }
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(universities, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"✓ {len(universities)} üniversite '{output_path}' dosyasına aktarıldı.")


def export_stats(output_path=STATS_PATH):
    """Bilgilendirme bölümünün gösterdiği veri sayılarını yazar."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT source, COUNT(*)
        FROM reviews
        GROUP BY source
        ORDER BY COUNT(*) DESC
        """
    )
    sources = [
        {"label": SOURCE_LABELS.get(source, source), "count": count}
        for source, count in cursor.fetchall()
    ]

    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reviews WHERE is_useful IS TRUE")
    useful_reviews = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT university_id) FROM reviews")
    universities_covered = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM universities")
    total_universities = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    stats = {
        "totalReviews": total_reviews,
        "usefulReviews": useful_reviews,
        "universitiesCovered": universities_covered,
        "totalUniversities": total_universities,
        "sources": sources,
        "updatedAt": date.today().isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"✓ İstatistikler '{output_path}' dosyasına aktarıldı.")


if __name__ == "__main__":
    export_universities()
    export_stats()
