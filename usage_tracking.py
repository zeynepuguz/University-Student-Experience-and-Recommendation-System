"""
OpenAI kullanımının kaydı.

Faturanın nereden geldiğini görmek için her OpenAI çağrısının token
sayısı iki yere yazılıyor:

1. Veritabanındaki `llm_usage` tablosu — her zaman çalışır, ek servis
   gerektirmez. `python -m usage_tracking` ile özet raporu alınır.
2. PostHog (POSTHOG_API_KEY varsa) — `$ai_generation` olayı olarak;
   PostHog'un "LLM analytics" ekranında grafik olarak görünür ve
   frontend'den gelen kullanıcı kimliğiyle eşleşir.

`feature` alanı çağrının nereden geldiğini söyler: "ask", "compare",
"query_embedding" (her soruda soru metninin embedding'i),
"index_embedding" (vector store kurulurken yorumların embedding'i),
"review_cleaner" (toplu temizlik betiği). Hangi kalemin faturayı
şişirdiği bu kolondan okunur.

Kayıt hiçbir koşulda asıl isteği bozmamalı: her hata yutulur.
"""

import os
import sys
import time
from contextvars import ContextVar

from dotenv import load_dotenv

from database import get_connection


load_dotenv()

# İsteği yapan ziyaretçinin PostHog kimliği; main.py her istekte
# X-Client-Id başlığından doldurur. Betiklerden gelen çağrılarda boş
# kalır ve "server" olarak kaydedilir.
client_id = ContextVar("client_id", default=None)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id SERIAL PRIMARY KEY,
    feature VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    client_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_table_ready = False

_posthog = None

if os.getenv("POSTHOG_API_KEY"):
    from posthog import Posthog

    _posthog = Posthog(
        os.getenv("POSTHOG_API_KEY"),
        host=os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")
    )


def ensure_table():
    """
    Kullanım tablosunu yoksa oluşturur. İlk kayıtta kendiliğinden
    çağrılıyor; böylece betikler (review_cleaner vb.) de ayrıca bir
    kurulum adımı gerektirmeden kayıt düşebiliyor.
    """

    global _table_ready

    if _table_ready:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE)

    conn.commit()

    cursor.close()
    conn.close()

    _table_ready = True


def record(feature, model, response, started_at):
    """
    Bir OpenAI cevabının token kullanımını kaydeder.

    `started_at`, çağrıdan hemen önce alınan time.monotonic() değeri.
    Chat cevaplarında usage.completion_tokens var; embedding
    cevaplarında yok (çıktı token'ı ücretlendirilmiyor).
    """

    try:
        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        latency_ms = int((time.monotonic() - started_at) * 1000)
        visitor = client_id.get()

        ensure_table()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO llm_usage (
                feature, model, input_tokens, output_tokens,
                latency_ms, client_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                feature,
                model,
                input_tokens,
                output_tokens,
                latency_ms,
                visitor
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        if _posthog:
            _posthog.capture(
                distinct_id=visitor or "server",
                event="$ai_generation",
                properties={
                    "$ai_provider": "openai",
                    "$ai_model": model,
                    "$ai_span_name": feature,
                    "$ai_input_tokens": input_tokens,
                    "$ai_output_tokens": output_tokens,
                    "$ai_latency": latency_ms / 1000,
                    # Ziyaretçi kimliği yoksa kişi profili açılmasın.
                    "$process_person_profile": visitor is not None
                }
            )
    except Exception as e:
        print(f"! Kullanım kaydedilemedi ({feature}): {e}", file=sys.stderr)


def capture(event, properties=None):
    """Sunucu tarafı bir olayı (örn. önbellek isabeti) PostHog'a gönderir."""

    if not _posthog:
        return

    try:
        visitor = client_id.get()

        _posthog.capture(
            distinct_id=visitor or "server",
            event=event,
            properties={
                **(properties or {}),
                "$process_person_profile": visitor is not None
            }
        )
    except Exception as e:
        print(f"! PostHog olayı gönderilemedi ({event}): {e}", file=sys.stderr)


def report(days=7):
    """
    Son `days` gündeki kullanımı özellik ve model bazında yazdırır.
    Faturanın hangi kalemden geldiğini görmenin en kısa yolu.
    """

    ensure_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            feature,
            model,
            COUNT(*),
            SUM(input_tokens),
            SUM(output_tokens)
        FROM llm_usage
        WHERE created_at > CURRENT_TIMESTAMP - make_interval(days => %s)
        GROUP BY feature, model
        ORDER BY SUM(input_tokens) + SUM(output_tokens) DESC
        """,
        (days,)
    )

    rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            DATE(created_at),
            COUNT(*),
            SUM(input_tokens),
            SUM(output_tokens)
        FROM llm_usage
        WHERE created_at > CURRENT_TIMESTAMP - make_interval(days => %s)
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
        """,
        (days,)
    )

    daily = cursor.fetchall()

    cursor.close()
    conn.close()

    print("\n" + "=" * 72)
    print(f"OPENAI KULLANIMI — son {days} gün")
    print("=" * 72)
    print(
        f"{'Özellik':<18}{'Model':<26}{'Çağrı':>8}"
        f"{'Girdi tok.':>11}{'Çıktı tok.':>11}"
    )

    for feature, model, calls, input_tokens, output_tokens in rows:
        print(
            f"{feature:<18}{model:<26}{calls:>8}"
            f"{input_tokens:>11}{output_tokens:>11}"
        )

    print("\nGün bazında:")

    for day, calls, input_tokens, output_tokens in daily:
        print(
            f"  {day}  {calls:>6} çağrı  "
            f"{input_tokens:>10} girdi  {output_tokens:>10} çıktı"
        )

    print(
        "\nDolar karşılığı için: platform.openai.com/usage "
        "(model fiyatları değişebildiği için burada hesaplanmıyor)."
    )


if __name__ == "__main__":
    from data_collection.console import force_utf8_output

    force_utf8_output()

    report(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
