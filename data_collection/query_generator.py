from data_collection.review_collector import get_all_universities


SEARCH_TEMPLATES = [
    '"{university}" öğrenci yorumları',
    '"{university}" öğrenci deneyimleri',
    '"{university}" kampüs hayatı',
    '"{university}" sosyal hayat',
    '"{university}" eğitim kalitesi',
    '"{university}" yurt imkanları',
    '"{university}" ulaşım',
]


def generate_queries(university_name):
    """
    Bir üniversite için otomatik arama sorguları üretir.
    """

    queries = []

    for template in SEARCH_TEMPLATES:
        query = template.format(university=university_name)
        queries.append(query)

    return queries


def generate_queries_for_all_universities():
    """
    Veritabanındaki tüm üniversiteler için
    otomatik arama sorguları üretir.
    """

    universities = get_all_universities()

    print(f"\nToplam üniversite sayısı: {len(universities)}")

    for university in universities:

        university_id = university[0]
        university_name = university[1]

        print("\n" + "=" * 60)
        print(
            f"Üniversite: {university_name} "
            f"| ID: {university_id}"
        )
        print("-" * 60)

        queries = generate_queries(university_name)

        for query in queries:
            print(query)


if __name__ == "__main__":
    generate_queries_for_all_universities()