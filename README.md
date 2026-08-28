# UniGuideAI

Üniversite tercihi yapacak öğrencilere yardımcı olan, **RAG (Retrieval-Augmented
Generation) tabanlı** bir üniversite keşif ve tercih asistanı.

Türkiye'deki üniversite öğrencilerinin YouTube yorumlarında, Ekşi Sözlük
girdilerinde ve ŞikayetVar şikayetlerinde paylaştığı **gerçek deneyimleri**
toplar, temizler, vektör veritabanına gömer ve bu verilere dayanarak
öğrencilerin sorularına kaynaklı, uydurmayan cevaplar üretir.

Sistem sadece genel bilgi ("bu üniversite iyidir/kötüdür") vermek yerine,
gerçek öğrencilerin ne söylediğine dayanır — ve elindeki yorumlar yetersizse
bunu açıkça belirtir, bilgi uydurmaz.

## Mimari

```
Üniversiteler (PostgreSQL)
        │
        ▼
Veri Toplama (YouTube API, Ekşi Sözlük, ŞikayetVar — scraping)
        │
        ▼
PostgreSQL (reviews tablosu, ham yorumlar)
        │
        ▼
LLM ile Temizlik (is_useful sınıflandırması — gpt-5.6-luna)
        │
        ▼
Export (.jsonl, LangChain Document formatı)
        │
        ▼
Embedding (text-embedding-3-small) + ChromaDB (kalıcı vector store)
        │
        ▼
RAG Sorgu (gpt-5.6-terra) — FastAPI backend
        │
        ▼
React Frontend
```

## Mevcut veri durumu

| Kaynak | Yorum sayısı |
|---|---|
| Ekşi Sözlük | 7104 |
| YouTube | 2678 |
| ŞikayetVar | 999 |
| **Toplam** | **10.781** (7652'si "işe yarar" olarak sınıflandırıldı) |

201/202 üniversitede en az bir kaynaktan yorum var.

## Proje yapısı

```
UniGuideAI/
├── data_collection/
│   ├── sources/
│   │   ├── youtube_collector.py     # YouTube Data API v3
│   │   ├── web_collector.py         # Ekşi Sözlük scraping
│   │   ├── sikayetvar_collector.py  # ŞikayetVar scraping
│   │   └── ...                      # (Instagram/TikTok/X/Facebook: kullanılmıyor,
│   │                                  bkz. proje notları — genel arama API'si yok)
│   ├── collector.py       # üniversite listesini toplar
│   ├── enricher.py        # üniversite şehir/tür/website bilgisini zenginleştirir
│   ├── query_generator.py # üniversite başına arama sorguları üretir
│   ├── review_collector.py # toplama, kaydetme, dedup, export orkestrasyonu
│   ├── review_cleaner.py  # LLM ile is_useful sınıflandırması
│   ├── vector_store.py    # embedding + ChromaDB
│   ├── rag.py              # RAG sorgu/karşılaştırma fonksiyonları
│   ├── chroma_db/          # (gitignore'da) kalıcı vector store
│   └── exports/            # (gitignore'da) reviews.jsonl
│
├── discovery/
│   └── search_engine.py    # (henüz boş, planlanan genel web keşfi)
│
├── frontend/                 # React + Vite arayüzü
├── main.py                  # FastAPI backend
├── schemas.py                # Pydantic şemaları
├── database.py                # PostgreSQL bağlantısı
└── .env                        # (git'e gönderilmez)
```

## Kurulum

### Backend

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`.env` dosyası oluştur (kök dizinde):

```
POSTGRESQL_HOST=...
POSTGRESQL_PORT=...
POSTGRESQL_DB=...
POSTGRESQL_USER=...
POSTGRESQL_PASSWORD=...

YOUTUBE_API_KEY=...
OPENAI_API_KEY=...

# Prod'da frontend'in gerçek adresi; boş bırakılırsa sadece
# localhost:5173'e izin verilir.
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

Backend'i çalıştır:

```bash
python -m uvicorn main:app --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` adresinde açılır, `http://127.0.0.1:8000`'deki
backend'e bağlanır.

## Canlıya alma (deployment)

Proje ücretsiz katmanlarla canlıya alınabilecek şekilde tasarlandı:

| Katman | Servis | Not |
|---|---|---|
| Veritabanı | [Neon](https://neon.tech) | Ücretsiz PostgreSQL, scale-to-zero |
| Backend | [Render](https://render.com) (free web service) | Kalıcı disk yok — vector store, açılışta veritabanından otomatik yeniden kurulur (`ensure_vector_store_ready()`, bkz. `main.py`) |
| Frontend | [Vercel](https://vercel.com) | Vite projelerini otomatik algılar |

**Önemli — maliyet koruması:** `/ask` ve `/compare` her çağrıda gerçek
OpenAI ücreti doğuruyor.

1. OpenAI hesabında **hard spending limit** (kesin harcama tavanı) ayarla:
   platform.openai.com → Billing → Limits.
2. Backend'de IP başına dakikada 10 istekle sınırlı rate limiting zaten
   aktif (`slowapi`, bkz. `main.py`).

**Adımlar (özet):**

1. Neon'da bir proje oluştur, `universities`/`reviews` şemasını ve mevcut
   veriyi (pg_dump/pg_restore ya da manuel export) taşı.
2. Render'da bu repodan bir "Web Service" oluştur:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment variables: `.env`'deki tüm değişkenler (Neon bağlantı
     bilgileriyle) + `ALLOWED_ORIGINS=<vercel-adresin>`
3. Vercel'de `frontend/` klasörünü bir proje olarak içe aktar,
   `VITE_API_URL=<render-backend-adresin>` ortam değişkenini ekle.

İlk istek, backend uykudan uyanıp vector store'u yeniden kurarken
(~1-3 dakika) yavaş olabilir; sonraki istekler normal hızda çalışır.

**Canlı adres:** _(henüz deploy edilmedi — deploy edildiğinde buraya eklenecek)_

## Veri toplama pipeline'ı

Her adım ayrı ayrı, elle çalıştırılır (henüz tek bir otomatik script yok):

```bash
# 1. YouTube'dan yorum topla (günlük API kotası: ~search sorgusu başına sınırlı)
python -m data_collection.review_collector

# 2. Ekşi Sözlük / ŞikayetVar toplu toplama (kota yok, tek seferde bitirilebilir)
python -c "from data_collection.review_collector import collect_web_reviews_for_all_universities; collect_web_reviews_for_all_universities(limit=202)"
python -c "from data_collection.review_collector import collect_sikayetvar_reviews_for_all_universities; collect_sikayetvar_reviews_for_all_universities(limit=202)"

# 3. Yeni toplanan yorumları LLM ile temizle
python -m data_collection.review_cleaner

# 4. RAG için export et
python -c "from data_collection.review_collector import export_reviews_for_rag; export_reviews_for_rag()"

# 5. Vector store'u güncelle (embed + ChromaDB'ye ekle, resume destekli)
python -m data_collection.vector_store
```

Tüm toplama fonksiyonları **resume** mantığıyla çalışır: bir üniversite için
belirli bir kaynaktan zaten yorum varsa o üniversite otomatik atlanır, bu
yüzden fonksiyonlar güvenle tekrar tekrar çalıştırılabilir.

## API uç noktaları

| Endpoint | Açıklama |
|---|---|
| `GET /universities` | Tüm üniversiteleri listeler |
| `POST /ask` | Tek bir üniversite (opsiyonel) hakkında soru sorar |
| `POST /compare` | İki üniversiteyi öğrencinin önceliğine göre karşılaştırır |

## Bilinen sınırlamalar

- Instagram, TikTok, X (Twitter) ve Facebook'ta herkese açık, ücretsiz bir
  arama API'si olmadığı için bu kaynaklar kullanılmıyor.
- YouTube Data API v3'ün "Search Queries per day" kotası oldukça düşük
  (günde ~13-14 üniversite işlenebiliyor), bu yüzden YouTube toplama süreci
  günler sürüyor.
- 5 üniversite için Ekşi Sözlük konusu, 1 üniversite için ŞikayetVar profili
  bulunamadı (isim eşleştirme sorunları).
