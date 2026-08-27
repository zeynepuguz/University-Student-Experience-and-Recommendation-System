import re
from datetime import date

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.sikayetvar.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}

TURKISH_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12
}


def slugify(university_name):
    """
    Üniversite adını ŞikayetVar'ın URL kalıbına (kirklareli-universitesi
    gibi) çevirir.
    """

    text = university_name.lower()

    replacements = {
        "ı": "i",
        "i̇": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
        "â": "a",
        "î": "i",
        "û": "u"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())

    return text


def parse_sikayetvar_date(date_text):
    """
    ŞikayetVar'ın "13 Ağustos 14:08" ya da "12 Ağustos 2025 11:48"
    biçimindeki tarihini veritabanına uygun "YYYY-AA-GG" biçimine çevirir.
    Yıl belirtilmemişse içinde bulunulan yıl varsayılır.
    """

    if not date_text:
        return None

    try:

        parts = date_text.strip().split()

        day = int(parts[0])
        month = TURKISH_MONTHS.get(parts[1].lower())

        if not month:
            return None

        if len(parts) == 4:
            year = int(parts[2])
        else:
            year = date.today().year

        return f"{year:04d}-{month:02d}-{day:02d}"

    except (ValueError, IndexError, KeyError):
        return None


def get_complaint_links(university_name):
    """
    Üniversitenin ŞikayetVar profil sayfasındaki şikayet
    detay linklerini getirir.
    """

    slug = slugify(university_name)
    url = f"{BASE_URL}/{slug}"

    response = requests.get(url, headers=HEADERS, timeout=20)

    if response.status_code != 200:
        return url, []

    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for article in soup.find_all("article"):

        heading = article.find("h3")

        if not heading:
            continue

        anchor = heading.find("a", href=True)

        if not anchor:
            continue

        complaint_url = anchor["href"]

        if complaint_url.startswith("/"):
            complaint_url = BASE_URL + complaint_url

        links.append(complaint_url)

    return url, links


def get_complaint_detail(complaint_url):
    """
    Bir şikayetin detay sayfasından tam metni ve tarihini getirir.
    """

    response = requests.get(complaint_url, headers=HEADERS, timeout=20)

    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    paragraph = soup.select_one("article p")

    if not paragraph:
        return None

    text = paragraph.get_text(" ", strip=True)

    if not text:
        return None

    date_span = soup.find("span", attrs={"aria-label": True})

    review_date = (
        parse_sikayetvar_date(date_span.get("aria-label"))
        if date_span else None
    )

    return {
        "text": text,
        "date": review_date
    }


def collect_sikayetvar_reviews(university_name, max_complaints=20):
    """
    Bir üniversite için ŞikayetVar'dan şikayet (yorum) toplar.

    `max_complaints`: en fazla bu kadar şikayetin detay sayfası
    çekilir (her biri ayrı bir istek olduğu için sınırlanıyor).
    """

    profile_url, complaint_links = get_complaint_links(university_name)

    if not complaint_links:
        print(f"Şikayet bulunamadı: {university_name}")
        return []

    print(
        f"Profil bulundu: {profile_url} "
        f"| toplam şikayet: {len(complaint_links)}"
    )

    all_reviews = []

    for complaint_url in complaint_links[:max_complaints]:

        detail = get_complaint_detail(complaint_url)

        if not detail:
            continue

        all_reviews.append({
            "review_text": detail["text"],
            "source": "sikayetvar",
            "review_date": detail["date"],

            "metadata": {
                "university_name": university_name,
                "topic_url": complaint_url
            }
        })

    return all_reviews


def test_collect_sikayetvar_reviews():

    university_name = "Boğaziçi Üniversitesi"

    reviews = collect_sikayetvar_reviews(
        university_name,
        max_complaints=5
    )

    print("\n" + "=" * 60)
    print(f"TOPLAM ŞİKAYET: {len(reviews)}")
    print("=" * 60)

    for index, review in enumerate(reviews, start=1):

        print(f"\n{index}. Şikayet")
        print(f"Yorum: {review['review_text'][:150]}")
        print(f"Tarih: {review['review_date']}")


if __name__ == "__main__":
    test_collect_sikayetvar_reviews()
