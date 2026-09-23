"""
Üniversite listesini frontend'e gömülecek statik bir JSON dosyasına aktarır.

Üniversite listesi pratikte sabit bir veri (yeni üniversite kurulması
dışında değişmiyor), ama sayfa açılışında backend'den çekiliyordu. Render'ın
ücretsiz katmanı backend'i uykuya aldığı için bu istek 1-3 dakika sürebiliyor
ve kullanıcı boş bir açılır liste görüyordu. Liste build'e gömülünce sayfa
backend'in durumundan bağımsız olarak anında dolu geliyor; taze liste arka
planda yine de çekilip üzerine yazılıyor.

Yeni üniversite eklendiğinde tekrar çalıştır:
    python -m data_collection.export_universities
"""

import json
import os

from data_collection.console import force_utf8_output
from database import get_connection

force_utf8_output()


OUTPUT_PATH = "frontend/src/universities.json"


def export_universities(output_path=OUTPUT_PATH):
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


if __name__ == "__main__":
    export_universities()
