import re

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.uludagsozluk.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}


def build_topic_url(university_name, page=1):
    """
    Üniversite adından Uludağ Sözlük konu adresini üretir.

    Site başlıkları adreste Türkçe karakterleriyle ve boşluklar
    tire olacak şekilde tutuyor (ör. "fırat-üniversitesi").
    """

    slug = university_name.strip().lower().replace(" ", "-")

    if page > 1:
        return f"{BASE_URL}/k/{slug}/{page}/"

    return f"{BASE_URL}/k/{slug}/"


def parse_entry_date(date_text):
    """
    "GG.AA.YYYY SS:DD" biçimindeki tarihi
    veritabanına uygun "YYYY-AA-GG" biçimine çevirir.
    """

    if not date_text:
        return None

    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", date_text)

    if not match:
        return None

    day, month, year = match.groups()

    return f"{year}-{month}-{day}"


def get_entries_from_page(university_name, page):
    """
    Bir konu sayfasındaki girdileri getirir.

    Girdi listesiyle birlikte konunun toplam sayfa sayısını
    da döndürür.
    """

    url = build_topic_url(university_name, page)

    response = requests.get(url, headers=HEADERS, timeout=20)

    if response.status_code != 200:
        return [], 1

    soup = BeautifulSoup(response.text, "html.parser")

    entries = []

    # Girdi "entry-<id>" bloğunda duruyor; bu blok hem metni
    # ("entry-body") hem de tarih/yazar satırını ("entry_area_<id>")
    # içeriyor. Metni iç bloktan alıyoruz ki arayüz yazıları
    # ("Loading...", "Şikayet et") yoruma karışmasın.
    for entry in soup.select("div[id^=entry-]"):

        entry_id = entry.get("id", "").replace("entry-", "")

        body = entry.find("div", class_="entry-body")

        text = body.get_text(" ", strip=True) if body else ""

        if not text:
            continue

        area = entry.find("div", id=f"entry_area_{entry_id}")

        entries.append({
            "text": text,
            "date": (
                area.get_text(" ", strip=True)
                if area else None
            )
        })

    slug = university_name.strip().lower().replace(" ", "-")

    page_numbers = [
        int(match.group(1))
        for link in soup.find_all("a", href=True)
        if (match := re.search(
            rf"/k/{re.escape(slug)}/(\d+)/?$",
            link["href"]
        ))
    ]

    page_count = max(page_numbers) if page_numbers else 1

    return entries, page_count


def collect_uludag_reviews(university_name, max_pages=5):
    """
    Bir üniversite için Uludağ Sözlük'ten girdi (yorum) toplar.

    `max_pages`: konu ne kadar uzun olursa olsun,
    en fazla bu kadar sayfa çekilir.
    """

    entries, page_count = get_entries_from_page(university_name, 1)

    if not entries:
        print(f"Konu bulunamadı: {university_name}")
        return []

    topic_url = build_topic_url(university_name)

    pages_to_fetch = min(page_count, max_pages)

    print(
        f"Konu bulundu: {topic_url}\n"
        f"Toplam sayfa: {page_count} "
        f"| çekilecek sayfa: {pages_to_fetch}"
    )

    def to_review(entry):
        return {
            "review_text": entry["text"],
            "source": "uludagsozluk",
            "review_date": parse_entry_date(entry["date"]),

            "metadata": {
                "university_name": university_name,
                "topic_url": topic_url
            }
        }

    all_reviews = [to_review(entry) for entry in entries]

    for page in range(2, pages_to_fetch + 1):

        print(f"Sayfa işleniyor: {page}")

        page_entries, _ = get_entries_from_page(university_name, page)

        all_reviews.extend(to_review(entry) for entry in page_entries)

    return all_reviews


def test_collect_uludag_reviews():

    university_name = "Kırklareli Üniversitesi"

    reviews = collect_uludag_reviews(
        university_name,
        max_pages=2
    )

    print("\n" + "=" * 60)
    print(f"TOPLAM GİRDİ: {len(reviews)}")
    print("=" * 60)

    for index, review in enumerate(reviews[:5], start=1):

        print(f"\n{index}. Girdi")
        print(f"Yorum: {review['review_text'][:150]}")
        print(f"Tarih: {review['review_date']}")


if __name__ == "__main__":
    test_collect_uludag_reviews()
