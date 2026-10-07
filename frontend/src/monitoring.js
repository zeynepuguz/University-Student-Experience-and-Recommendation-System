import * as Sentry from "@sentry/react";
import posthog from "posthog-js";

// Canlı izleme. Anahtarlar Vercel'deki ortam değişkenlerinden gelir;
// tanımlı değillerse (örn. yerelde) ilgili servis hiç başlatılmaz.
//
// - Sentry: tarayıcıda oluşan JS hataları + backend'e giden isteklerin
//   süreleri.
// - PostHog: ziyaretçi olayları (soru soruldu, cevap geldi/gelmedi)
//   ve oturum kaydı (fare hareketleri, tıklamalar). Oturum kaydı
//   PostHog proje ayarlarından açılır.

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const POSTHOG_KEY = import.meta.env.VITE_POSTHOG_KEY;
const POSTHOG_HOST =
  import.meta.env.VITE_POSTHOG_HOST || "https://eu.i.posthog.com";

export function initMonitoring(apiUrl) {
  if (SENTRY_DSN) {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: import.meta.env.MODE,
      integrations: [Sentry.browserTracingIntegration()],
      tracesSampleRate: 0.2,
      // Backend isteklerine iz başlığı eklenir; frontend ve backend
      // hataları Sentry'de aynı iz altında görünür.
      tracePropagationTargets: [apiUrl]
    });
  }

  if (POSTHOG_KEY) {
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      // Anonim ziyaretçiler için kişi profili açılmıyor (ücretsiz
      // kotayı korur); olaylar ve oturum kayıtları yine tutulur.
      person_profiles: "identified_only"
    });
  }
}

// Ziyaretçinin PostHog kimliği; backend'e X-Client-Id olarak gönderilir
// ki token harcaması aynı ziyaretçiyle eşleşsin.
export function clientIdHeader() {
  if (!POSTHOG_KEY) {
    return {};
  }

  return { "X-Client-Id": posthog.get_distinct_id() };
}

export function track(event, properties) {
  if (POSTHOG_KEY) {
    posthog.capture(event, properties);
  }
}
