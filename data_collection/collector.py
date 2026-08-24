import requests
from bs4 import BeautifulSoup
from database import get_connection


def get_page(url: str):
    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "UniGuideAI/1.0"
        }
    )

    response.raise_for_status()

    return response.text


def collect_university_names():
    url = "https://www.turkiye.gov.tr/universite-hizmet-listesi"

    html = get_page(url)
    soup = BeautifulSoup(html, "html.parser")

    universities = []

    for heading in soup.find_all("h3"):
        name = heading.get_text(strip=True)

        if "Üniversitesi" in name or "Enstitüsü" in name:
            universities.append(name)

    return universities


def save_universities(universities):
    conn = get_connection()
    cursor = conn.cursor()

    for name in universities:
        cursor.execute("""
            INSERT INTO universities (name)
            VALUES (%s)
            ON CONFLICT (name) DO NOTHING
        """, (name,))

    conn.commit()

    cursor.close()
    conn.close()


if __name__ == "__main__":
    universities = collect_university_names()

    print(f"Bulunan üniversite sayısı: {len(universities)}")

    save_universities(universities)

    print("Üniversiteler PostgreSQL'e kaydedildi!")