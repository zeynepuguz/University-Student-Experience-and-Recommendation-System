import os
import requests
from dotenv import load_dotenv


load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

BASE_URL = "https://www.googleapis.com/youtube/v3"


def search_videos(query, max_results=5):
    """
    Verilen sorguya göre YouTube videolarını bulur.
    """

    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY bulunamadı.")
        return []

    url = f"{BASE_URL}/search"

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "relevanceLanguage": "tr"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    videos = []

    for item in data.get("items", []):

        video_id = item.get("id", {}).get("videoId")

        # Bazı sonuç öğelerinde videoId bulunmayabilir
        # (ör. video dışı/kısıtlı bir öğe); bu öğeyi atla.
        if not video_id:
            continue

        video = {
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "channel_title": item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
            "url": f"https://www.youtube.com/watch?v={video_id}"
        }

        videos.append(video)

    return videos


def get_video_comments(video_id, max_results=30):
    """
    Belirli bir YouTube videosunun yorumlarını getirir.
    """

    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY bulunamadı.")
        return []

    url = f"{BASE_URL}/commentThreads"

    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "textFormat": "plainText"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    if response.status_code != 200:
        print(
            f"Video yorumları alınamadı. "
            f"Video ID: {video_id}"
        )
        return []

    data = response.json()

    comments = []

    for item in data.get("items", []):

        snippet = item["snippet"]["topLevelComment"]["snippet"]

        comment = {
            "review_text": snippet["textDisplay"],
            "review_date": snippet["publishedAt"],
            "author": snippet["authorDisplayName"],
            "like_count": snippet["likeCount"],
            "video_id": video_id
        }

        comments.append(comment)

    return comments


def create_search_queries(university_name):
    """
    Bir üniversite için farklı YouTube arama sorguları oluşturur.
    """

    return [
        f"{university_name} öğrenci yorumları",
        f"{university_name} nasıl",
        f"{university_name} öğrenci hayatı",
        f"{university_name} kampüs",
        f"{university_name} deneyim",
        f"{university_name} memnuniyet",
        f"{university_name} vlog"
    ]


def is_relevant_video(video, university_name):
    """
    Videonun gerçekten hedef üniversiteyle
    alakalı olup olmadığını kontrol eder.
    """

    title = video["title"].lower()
    university_name = university_name.lower()

    # Üniversitenin tam adı başlıkta geçiyorsa
    if university_name in title:
        return True

    # Üniversite adındaki bazı önemli kelimeleri kontrol et
    words = university_name.split()

    matched_words = 0

    for word in words:
        if len(word) > 3 and word in title:
            matched_words += 1

    # En az 2 anlamlı kelime eşleşirse
    if matched_words >= 2:
        return True

    return False


def is_useful_comment(comment_text):
    """
    Spam, anlamsız veya çok kısa yorumları filtreler.
    """

    if not comment_text:
        return False

    comment_text = comment_text.strip()

    # Çok kısa yorumları alma
    if len(comment_text) < 20:
        return False

    normalized_text = comment_text.lower()

    spam_phrases = [
        "ilk",
        "abone oldum",
        "kanalıma",
        "çok güzel video",
        "eline sağlık",
        "helal olsun",
        "buradayım",
        "selam",
        "link bırakıyorum",
        "haber kanalı",
        "kanalı takip"
    ]

    for phrase in spam_phrases:
        if phrase in normalized_text:
            return False

    return True


def collect_youtube_reviews(
    university_name,
    max_videos_per_query=3,
    max_comments=30
):
    """
    Bir üniversite hakkında YouTube videolarını
    ve bu videoların faydalı yorumlarını toplar.
    """

    search_queries = create_search_queries(
        university_name
    )

    all_videos = {}

    print("\n" + "=" * 60)
    print(f"ÜNİVERSİTE: {university_name}")
    print("=" * 60)

    # Farklı sorgularla video ara
    for query in search_queries:

        print(f"\nAranıyor: {query}")

        videos = search_videos(
            query=query,
            max_results=max_videos_per_query
        )

        for video in videos:

            # Aynı videoyu tekrar ekleme
            video_id = video["video_id"]

            if video_id not in all_videos:
                all_videos[video_id] = video

    print("\n" + "=" * 60)
    print(f"TOPLAM BULUNAN BENZERSİZ VIDEO: {len(all_videos)}")
    print("=" * 60)

    relevant_videos = []

    # Videoları filtrele
    for video in all_videos.values():

        if is_relevant_video(
            video,
            university_name
        ):

            relevant_videos.append(video)

            print(
                f"\n✓ İLGİLİ VIDEO:\n"
                f"{video['title']}"
            )

        else:

            print(
                f"\n✗ ELENDİ:\n"
                f"{video['title']}"
            )

    print("\n" + "=" * 60)
    print(f"İLGİLİ VIDEO SAYISI: {len(relevant_videos)}")
    print("=" * 60)

    all_reviews = []

    # İlgili videoların yorumlarını al
    for video in relevant_videos:

        print(
            f"\nVideo işleniyor: "
            f"{video['title']}"
        )

        comments = get_video_comments(
            video_id=video["video_id"],
            max_results=max_comments
        )

        for comment in comments:

            comment_text = comment["review_text"]

            # Şimdilik filtreleme yapılmıyor; ham veri toplanıyor.
            # Temizlik/ilgi tespiti ileride enrichment aşamasında yapılacak.

            review = {
                "review_text": comment_text,
                "source": "youtube_comment",
                "review_date": comment["review_date"],

                "metadata": {
                    "university_name": university_name,

                    "video_id": video["video_id"],

                    "video_title": video["title"],

                    "video_url": video["url"],

                    "channel_title": (
                        video["channel_title"]
                    ),

                    "like_count": (
                        comment["like_count"]
                    )
                }
            }

            all_reviews.append(review)

    return all_reviews


def test_collect_youtube_reviews():

    university_name = "Kırklareli Üniversitesi"

    reviews = collect_youtube_reviews(
        university_name=university_name,
        max_videos_per_query=3,
        max_comments=30
    )

    print("\n" + "=" * 60)
    print(f"TOPLAM FAYDALI YORUM: {len(reviews)}")
    print("=" * 60)

    for index, review in enumerate(
        reviews,
        start=1
    ):

        print(f"\n{index}. Yorum")

        print(
            f"Yorum: "
            f"{review['review_text']}"
        )

        print(
            f"Kaynak: "
            f"{review['source']}"
        )

        print(
            f"Video: "
            f"{review['metadata']['video_title']}"
        )

        print(
            f"Beğeni: "
            f"{review['metadata']['like_count']}"
        )


if __name__ == "__main__":
    test_collect_youtube_reviews()