from fastapi import FastAPI
from database import get_connection
from schemas import UniversityCreate
from schemas import UniversityCreate, ReviewCreate



app = FastAPI()


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