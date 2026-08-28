import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import get_connection
from schemas import UniversityCreate, ReviewCreate, AskRequest, CompareRequest
from data_collection.rag import ask, compare
from data_collection.vector_store import ensure_vector_store_ready


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kalıcı disk olmayan ortamlarda (örn. ücretsiz hosting) vector
    # store'u veritabanından yeniden kurar; doluysa dokunmaz.
    #
    # Arka planda (ayrı bir thread'de) çalıştırılıyor ki bu işlem
    # (birkaç dakika sürebiliyor) uygulamanın portu açmasını
    # bloklamasın — yoksa Render'ın port taraması zaman aşımına uğrar.
    asyncio.create_task(asyncio.to_thread(ensure_vector_store_ready))
    yield


app = FastAPI(lifespan=lifespan)

# CORS: prod'da ALLOWED_ORIGINS ortam değişkeniyle (virgülle ayrılmış)
# ayarlanır; yoksa sadece yerel geliştirme sunucusuna izin verilir.
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting: /ask ve /compare her çağrıda gerçek OpenAI maliyeti
# doğuruyor, bu yüzden IP başına sınırlandırılıyor.
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
@limiter.limit("10/minute")
def ask_question(request: Request, payload: AskRequest):
    answer = ask(
        payload.question,
        university_name=payload.university_name
    )

    return {
        "question": payload.question,
        "university_name": payload.university_name,
        "answer": answer
    }


@app.post("/compare")
@limiter.limit("10/minute")
def compare_universities(request: Request, payload: CompareRequest):
    answer = compare(
        payload.question,
        payload.university_names
    )

    return {
        "question": payload.question,
        "university_names": payload.university_names,
        "answer": answer
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
