from database import get_connection
import requests
from bs4 import BeautifulSoup
import re


BASE_URL = "https://www.universitetercih.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# Sayfadan otomatik çekilemeyen özel üniversiteler
MANUAL_UNIVERSITY_DATA = {
    "Ahmet Yesevi Üniversitesi": {
        "city": "Türkistan",
        "university_type": "Yurt Dışı",
        "website": "https://www.ayu.edu.tr/"
    },

    "Manisa Celal Bayar Üniversitesi": {
        "city": "Manisa",
        "university_type": "Devlet",
        "website": "https://cbu.edu.tr"
    }
}


def normalize_name(name):
    name = name.lower()

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
        name = name.replace(old, new)

    name = re.sub(r"[^a-z0-9]", "", name)

    return name


def get_universities_with_missing_data():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name
        FROM universities
        WHERE city IS NULL
           OR university_type IS NULL
           OR website IS NULL
    """)

    universities = cursor.fetchall()

    cursor.close()
    conn.close()

    return universities


def get_university_urls():
    url = f"{BASE_URL}/universiteler"

    response = requests.get(
        url,
        timeout=20,
        headers=HEADERS
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    university_urls = {}

    for link in soup.find_all("a", href=True):
        name = link.get_text(" ", strip=True)
        href = link["href"]

        # Üniversite detay sayfası olan linkleri al
        if name and "/universite/" in href:

            if href.startswith("/"):
                href = BASE_URL + href

            university_urls[name] = href

    return university_urls


def find_best_matching_url(
    university_name,
    university_urls
):
    normalized_target = normalize_name(
        university_name
    )

    # 1. Tam normalize edilmiş eşleşme
    for source_name, source_url in university_urls.items():

        normalized_source = normalize_name(
            source_name
        )

        if normalized_source == normalized_target:

            print(
                f"Benzer isim eşleşti: "
                f"{source_name}"
            )

            return source_name, source_url

    # 2. Kısmi eşleşme
    for source_name, source_url in university_urls.items():

        normalized_source = normalize_name(
            source_name
        )

        if (
            normalized_target in normalized_source
            or normalized_source in normalized_target
        ):

            print(
                f"Kısmi eşleşme bulundu: "
                f"{university_name} -> {source_name}"
            )

            return source_name, source_url

    # 3. Özel alias eşleşmeleri
    aliases = {
        "Ahmet Yesevi Üniversitesi": [
            "Hoca Ahmet Yesevi Uluslararası Türk-Kazak Üniversitesi (Türkistan-Kazakistan)"
        ],

        "Manisa Celal Bayar Üniversitesi": [
            "Manisa Celâl Bayar Üniversitesi",
            "Celal Bayar Üniversitesi"
        ]
    }

    if university_name in aliases:

        for alias in aliases[university_name]:

            normalized_alias = normalize_name(
                alias
            )

            for source_name, source_url in university_urls.items():

                normalized_source = normalize_name(
                    source_name
                )

                if (
                    normalized_source == normalized_alias
                    or normalized_alias in normalized_source
                    or normalized_source in normalized_alias
                ):

                    print(
                        f"Alias eşleşti: "
                        f"{university_name} -> {source_name}"
                    )

                    return source_name, source_url

    return None, None


def get_university_details(name, url):

    response = requests.get(
        url,
        timeout=20,
        headers=HEADERS
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    texts = list(
        soup.stripped_strings
    )

    city = None
    university_type = None
    website = None

    # Üniversite adının geçtiği konumları bul
    name_indexes = [
        i
        for i, text in enumerate(texts)
        if text == name
    ]

    # Ana bilgi bloğundan şehir ve türü bul
    for name_index in name_indexes:

        next_texts = texts[
            name_index:name_index + 10
        ]

        # Örnek:
        #
        # Abdullah Gül Üniversitesi
        # Kayseri
        # / Kocasinan
        # Devlet
        # Üniversitesi

        if (
            len(next_texts) >= 5
            and next_texts[2].startswith("/")
            and next_texts[4] == "Üniversitesi"
        ):

            city = next_texts[1]
            university_type = next_texts[3]

            break

    # Kurumsal Bilgiler kısmından tür bilgisini al
    try:

        corporate_index = texts.index(
            "Kurumsal Bilgiler"
        )

        corporate_texts = texts[
            corporate_index:corporate_index + 40
        ]

        for i, text in enumerate(corporate_texts):

            if (
                text == "Tür"
                and i + 1 < len(corporate_texts)
            ):

                university_type = corporate_texts[
                    i + 1
                ]

                break

    except ValueError:
        pass

    # Web sitesi linkini bul
    for link in soup.find_all(
        "a",
        href=True
    ):

        text = link.get_text(
            " ",
            strip=True
        )

        href = link["href"]

        if text == "Web Sitesi":

            if href.startswith("http"):

                website = href

                break

    return {
        "name": name,
        "city": city,
        "university_type": university_type,
        "website": website
    }


def update_universities():

    universities = (
        get_universities_with_missing_data()
    )

    university_urls = (
        get_university_urls()
    )

    failed_universities = []

    conn = get_connection()
    cursor = conn.cursor()

    print(
        f"\nGüncellenecek üniversite sayısı: "
        f"{len(universities)}"
    )

    updated_count = 0
    failed_count = 0

    for university_id, university_name in universities:

        print(
            f"\nİşleniyor: "
            f"{university_name}"
        )

        try:

            # ==================================
            # 1. MANUEL VERİ KONTROLÜ
            # ==================================

            if university_name in MANUAL_UNIVERSITY_DATA:

                details = MANUAL_UNIVERSITY_DATA[
                    university_name
                ]

                print("Manuel veri bulundu.")

            else:

                # ==================================
                # 2. ÜNİVERSİTE URL'SİNİ BUL
                # ==================================

                source_name, url = (
                    find_best_matching_url(
                        university_name,
                        university_urls
                    )
                )

                if not source_name or not url:

                    print("URL bulunamadı!")

                    failed_universities.append(
                        university_name
                    )

                    failed_count += 1

                    continue

                print(
                    f"Kaynak adı: "
                    f"{source_name}"
                )

                print(
                    f"URL: "
                    f"{url}"
                )

                # ==================================
                # 3. SAYFADAN BİLGİLERİ ÇEK
                # ==================================

                details = get_university_details(
                    source_name,
                    url
                )

            # ==================================
            # 4. VERİLER TAM MI?
            # ==================================

            if (
                details["city"]
                and details["university_type"]
                and details["website"]
            ):

                cursor.execute("""
                    UPDATE universities
                    SET city = %s,
                        university_type = %s,
                        website = %s
                    WHERE id = %s
                """, (
                    details["city"],
                    details["university_type"],
                    details["website"],
                    university_id
                ))

                updated_count += 1

                print(
                    f"✓ Güncellendi -> "
                    f"{details['city']} | "
                    f"{details['university_type']} | "
                    f"{details['website']}"
                )

            else:

                print(
                    "! Eksik bilgi bulundu:"
                )

                print(
                    f"  Şehir: "
                    f"{details['city']}"
                )

                print(
                    f"  Tür: "
                    f"{details['university_type']}"
                )

                print(
                    f"  Website: "
                    f"{details['website']}"
                )

                failed_universities.append(
                    university_name
                )

                failed_count += 1

        except Exception as e:

            print(f"! Hata: {e}")

            failed_universities.append(
                university_name
            )

            failed_count += 1

    # ==================================
    # FOR DÖNGÜSÜ BİTTİ
    # ==================================

    conn.commit()

    cursor.close()
    conn.close()

    print("\n" + "=" * 50)
    print("GÜNCELLEME TAMAMLANDI")
    print(f"Güncellenen: {updated_count}")
    print(f"Başarısız: {failed_count}")
    print(
        f"Başarısız Üniversiteler: "
        f"{failed_universities}"
    )


if __name__ == "__main__":
    update_universities()