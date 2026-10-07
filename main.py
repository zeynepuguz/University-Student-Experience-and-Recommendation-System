import os
import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import usage_tracking
from database import get_connection
from answer_cache import (
    build_key,
    ensure_table,
    get_cached_answer,
    store_answer
)
from schemas import UniversityCreate, ReviewCreate, AskRequest, CompareRequest
from data_collection.rag import ask, compare, NO_REVIEWS_ANSWER
from data_collection.vector_store import ensure_vector_store_ready, is_ready


# Hata takibi: SENTRY_DSN tanımlıysa yakalanmayan her hata (500'ler,
# OpenAI/veritabanı hataları) Sentry'ye gider. FastAPI uygulaması
# oluşturulmadan önce başlatılmalı. Tanımlı değilse (yerelde) hiçbir
# şey yapmaz.
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        # İsteklerin %20'si için performans (süre) verisi.
        traces_sample_rate=float(
            os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")
        ),
        # IP ve başlık gibi kişisel veriler gönderilmiyor.
        send_default_pii=False,
    )


def remember_visitor(request: Request):
    """
    Frontend'in X-Client-Id başlığında gönderdiği PostHog kimliğini
    kullanım kaydına bağlar; böylece token harcaması ziyaretçi
    bazında görülebiliyor.
    """

    visitor = request.headers.get("x-client-id")

    usage_tracking.client_id.set(visitor[:100] if visitor else None)


def require_vector_store():
    """
    Açılıştaki vector store kurulumu bitmeden önbellekte olmayan bir
    soruya cevap üretilmiyor: yorumları henüz eklenmemiş üniversiteler
    için "yeterli yorum yok" gibi yanlış bir cevap çıkıyordu.
    """

    if not is_ready():
        raise HTTPException(
            status_code=503,
            detail="Asistan hazırlanıyor, 1-2 dakika sonra tekrar dene."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kalıcı disk olmayan ortamlarda (örn. ücretsiz hosting) vector
    # store'u veritabanından yeniden kurar; doluysa dokunmaz.
    #
    # Arka planda (ayrı bir thread'de) çalıştırılıyor ki bu işlem
    # (birkaç dakika sürebiliyor) uygulamanın portu açmasını
    # bloklamasın — yoksa Render'ın port taraması zaman aşımına uğrar.
    ensure_table()

    asyncio.create_task(asyncio.to_thread(ensure_vector_store_ready))
    yield


app = FastAPI(lifespan=lifespan)

# CORS: prod'da ALLOWED_ORIGINS ortam değişkeniyle (virgülle ayrılmış)
# ayarlanır; yoksa sadece yerel geliştirme sunucusuna izin verilir.
# .strip() olası baştaki/sondaki boşluk ya da satır sonu karakterlerini
# temizliyor (env var panellerinde bazen fark edilmeden eklenebiliyor).
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting: /ask ve /compare her çağrıda gerçek OpenAI maliyeti
# doğuruyor, bu yüzden IP başına sınırlandırılıyor. Dakikalık limitin
# yanına günlük bir tavan da konuyor: dakikada 10 istek, gün boyu
# sürdürülürse tek bir ziyaretçi bile faturayı uçurabiliyor.
# ASK_RATE_LIMIT ile ortam değişkeninden ayarlanabilir.
ASK_RATE_LIMIT = os.getenv("ASK_RATE_LIMIT", "5/minute;40/day")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/")
def home():
    return {"message": "UniGuide AI backend is running!"}




@app.get("/universities")
def get_universities():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, city, university_type, website
        FROM universities
    """)

    universities = cursor.fetchall()

    cursor.close()
    conn.close()

    result = []

    for university in universities:
        result.append({
            "id": university[0],
            "name": university[1],
            "city": university[2],
            "university_type": university[3],
            "website": university[4]
        })

    return result




@app.post("/universities")
def create_university(university: UniversityCreate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO universities (name, city, university_type, website)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, city, university_type, website
    """, (
        university.name,
        university.city,
        university.university_type,
        university.website
    ))

    new_university = cursor.fetchone()

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "id": new_university[0],
        "name": new_university[1],
        "city": new_university[2],
        "university_type": new_university[3],
        "website": new_university[4]
    }





@app.post("/reviews")
def create_review(review: ReviewCreate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reviews (
            university_id,
            review_text,
            source,
            review_date
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id, university_id, review_text, source, review_date
    """, (
        review.university_id,
        review.review_text,
        review.source,
        review.review_date
    ))

    new_review = cursor.fetchone()

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "id": new_review[0],
        "university_id": new_review[1],
        "review_text": new_review[2],
        "source": new_review[3],
        "review_date": new_review[4]
    }


@app.post("/ask")
@limiter.limit(ASK_RATE_LIMIT)
def ask_question(request: Request, payload: AskRequest):
    remember_visitor(request)

    cache_key = build_key(payload.question, [payload.university_name])

    answer = get_cached_answer(cache_key)
    cached = answer is not None

    usage_tracking.capture(
        "answer_served",
        {"feature": "ask", "cached": cached}
    )

    if not cached:
        require_vector_store()

        answer = ask(
            payload.question,
            university_name=payload.university_name
        )

        if answer != NO_REVIEWS_ANSWER:
            store_answer(
                cache_key,
                payload.question,
                [payload.university_name],
                answer
            )

    return {
        "question": payload.question,
        "university_name": payload.university_name,
        "answer": answer,
        "cached": cached
    }


@app.post("/compare")
@limiter.limit(ASK_RATE_LIMIT)
def compare_universities(request: Request, payload: CompareRequest):
    remember_visitor(request)

    cache_key = build_key(payload.question, payload.university_names)

    answer = get_cached_answer(cache_key)
    cached = answer is not None

    usage_tracking.capture(
        "answer_served",
        {"feature": "compare", "cached": cached}
    )

    if not cached:
        require_vector_store()

        answer = compare(
            payload.question,
            payload.university_names
        )

        store_answer(
            cache_key,
            payload.question,
            payload.university_names,
            answer
        )

    return {
        "question": payload.question,
        "university_names": payload.university_names,
        "answer": answer,
        "cached": cached
    }


@app.get("/universities/{university_id}/reviews")
def get_university_reviews(university_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, university_id, review_text, source, review_date
        FROM reviews
        WHERE university_id = %s
    """, (university_id,))

    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        {
            "id": review[0],
            "university_id": review[1],
            "review_text": review[2],
            "source": review[3],
            "review_date": review[4]
        }
        for review in reviews
    ]
