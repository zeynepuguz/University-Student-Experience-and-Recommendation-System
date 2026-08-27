import requests
from bs4 import BeautifulSoup


BASE_URL = "https://eksisozluk.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}


def find_topic_url(university_name):
    """
    Ekşi Sözlük'te üniversiteye ait konuyu (topic) arar.
    Bulursa konunun URL'sini, bulamazsa None döndürür.
    """

    response = requests.get(
        f"{BASE_URL}/",
        params={"q": university_name},
        headers=HEADERS,
        timeout=20
    )

    if response.status_code != 200:
        return None

    return response.url


def parse_entry_date(date_text):
    """
    Ekşi Sözlük'ün "GG.AA.YYYY SS:DD" biçimindeki
    tarihini veritabanına uygun "YYYY-AA-GG" biçimine çevirir.
    """

    if not date_text:
        return None

    try:

        date_part = date_text.strip().split(" ")[0]

        day, month, year = date_part.split(".")

        return f"{year}-{month}-{day}"

    except (ValueError, IndexError):
        return None


def get_entries_from_page(topic_url, page):
    """
    Bir Ekşi Sözlük konu sayfasının belirli bir
    sayfasındaki girdileri (entry) getirir.

    Girdi listesiyle birlikte konunun toplam sayfa
    sayısını da döndürür.
    """

    response = requests.get(
        topic_url,
        params={"p": page},
        headers=HEADERS,
        timeout=20
    )

    if response.status_code != 200:
        return [], 1

    soup = BeautifulSoup(response.text, "html.parser")

    entry_list = soup.find("ul", id="entry-item-list")

    entries = []

    if entry_list:

        for item in entry_list.find_all("li"):

            content = item.find("div", class_="content")

            if not content:
                continue

            date = item.find("a", class_="entry-date")

            entries.append({
                "text": content.get_text(" ", strip=True),
                "date": (
                    date.get_text(strip=True)
                    if date else None
                )
            })

    pager = soup.find("div", class_="pager")

    page_count = 1

    if pager and pager.get("data-pagecount"):
        page_count = int(pager.get("data-pagecount"))

    return entries, page_count


def collect_web_reviews(university_name, max_pages=5):
    """
    Bir üniversite için Ekşi Sözlük'ten girdi (yorum) toplar.

    `max_pages`: konu ne kadar uzun olursa olsun,
    en fazla bu kadar sayfa çekilir.
    """

    topic_url = find_topic_url(university_name)

    if not topic_url:
        print(f"Konu bulunamadı: {university_name}")
        return []

    print(f"Konu bulundu: {topic_url}")

    all_reviews = []

    entries, page_count = get_entries_from_page(topic_url, 1)

    pages_to_fetch = min(page_count, max_pages)

    print(
        f"Toplam sayfa: {page_count} "
        f"| çekilecek sayfa: {pages_to_fetch}"
    )

    for entry in entries:

        all_reviews.append({
            "review_text": entry["text"],
            "source": "eksisozluk",
            "review_date": parse_entry_date(entry["date"]),

            "metadata": {
                "university_name": university_name,
                "topic_url": topic_url
            }
        })

    for page in range(2, pages_to_fetch + 1):

        print(f"Sayfa işleniyor: {page}")

        page_entries, _ = get_entries_from_page(topic_url, page)

        for entry in page_entries:

            all_reviews.append({
                "review_text": entry["text"],
                "source": "eksisozluk",
                "review_date": parse_entry_date(entry["date"]),

                "metadata": {
                    "university_name": university_name,
                    "author": entry["author"],
                    "topic_url": topic_url
                }
            })

    return all_reviews


def test_collect_web_reviews():

    university_name = "Kırklareli Üniversitesi"

    reviews = collect_web_reviews(
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
    test_collect_web_reviews()
