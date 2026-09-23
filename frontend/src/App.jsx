import { useEffect, useState } from "react";
import "./App.css";
import universitiesSnapshot from "./universities.json";

// Prod'da .env.production içindeki VITE_API_URL kullanılır
// (bkz. frontend/.env.production.example); yoksa yerel backend'e düşer.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// Üniversite listesi pratikte sabit bir veri, ama backend'den çekiliyordu:
// Render'ın ücretsiz katmanı backend'i uykuya aldığı için bu istek 1-3
// dakika sürebiliyor ve o süre boyunca açılır liste boş kalıyordu. Liste
// artık build'e gömülü (universities.json, `python -m
// data_collection.export_universities` ile üretilir), yani backend'in
// durumundan bağımsız olarak anında dolu geliyor. Taze liste yine de arka
// planda çekilip üzerine yazılıyor, böylece yeni eklenen bir üniversite
// build beklemeden görünür.
const CACHE_KEY = "uniguide.universities";

function readCachedUniversities() {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    const parsed = cached ? JSON.parse(cached) : null;

    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed;
    }
  } catch {
    // Bozuk/erişilemeyen cache önemli değil, gömülü listeye düşeriz.
  }

  return universitiesSnapshot;
}

function formatAnswer(text) {
  // "**kalın**" işaretlerini basitçe <strong>'a çevirir,
  // satır sonlarını korur. Tam bir markdown motoru değil,
  // model çıktısındaki yaygın kalıpları karşılamak için yeterli.
  const paragraphs = text.split("\n\n");

  return paragraphs.map((paragraph, pIndex) => {
    const parts = paragraph.split(/(\*\*[^*]+\*\*)/g);

    return (
      <p key={pIndex}>
        {parts.map((part, index) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={index}>{part.slice(2, -2)}</strong>;
          }
          return part;
        })}
      </p>
    );
  });
}

function App() {
  const [universities, setUniversities] = useState(readCachedUniversities);
  const [mode, setMode] = useState("ask");

  // Tek soru modu
  const [universityName, setUniversityName] = useState("");
  const [question, setQuestion] = useState("");

  // Karşılaştırma modu
  const [universityA, setUniversityA] = useState("");
  const [universityB, setUniversityB] = useState("");
  const [compareQuestion, setCompareQuestion] = useState("");

  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    // Liste zaten ekranda; bu istek sadece taze veriyi almak için. Backend
    // uykudaysa uyanması 1-3 dakika sürebildiğinden birkaç kez tekrar
    // deniyoruz, ama kullanıcıya hiçbir bekleme/hata göstermiyoruz —
    // başarısız olsa bile gömülü liste kullanılmaya devam eder.
    async function refreshUniversities(attempt = 0) {
      try {
        const response = await fetch(`${API_URL}/universities`);

        if (!response.ok) {
          throw new Error("Sunucu hatası");
        }

        const data = await response.json();

        if (cancelled || !Array.isArray(data) || data.length === 0) {
          return;
        }

        setUniversities(data);

        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify(data));
        } catch {
          // Kota dolu ya da depolama kapalıysa sorun değil.
        }
      } catch {
        if (!cancelled && attempt < 12) {
          setTimeout(() => refreshUniversities(attempt + 1), 15000);
        }
      }
    }

    refreshUniversities();

    return () => {
      cancelled = true;
    };
  }, []);

  function switchMode(nextMode) {
    setMode(nextMode);
    setAnswer(null);
    setError(null);
  }

  async function handleAskSubmit(event) {
    event.preventDefault();

    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          university_name: universityName || null
        })
      });

      if (!response.ok) {
        throw new Error("Sunucu hatası");
      }

      const data = await response.json();
      setAnswer(data.answer);
    } catch {
      setError(
        "Bir şeyler ters gitti. Backend çalışıyor mu kontrol et."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCompareSubmit(event) {
    event.preventDefault();

    if (!compareQuestion.trim() || !universityA || !universityB) {
      return;
    }

    if (universityA === universityB) {
      setError("Karşılaştırmak için iki farklı üniversite seç.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const response = await fetch(`${API_URL}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: compareQuestion,
          university_names: [universityA, universityB]
        })
      });

      if (!response.ok) {
        throw new Error("Sunucu hatası");
      }

      const data = await response.json();
      setAnswer(data.answer);
    } catch {
      setError(
        "Bir şeyler ters gitti. Backend çalışıyor mu kontrol et."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <h1>UniGuideAI</h1>
        <p>Gerçek öğrenci yorumlarına dayalı üniversite asistanı</p>
      </header>

      <div className="mode-tabs">
        <button
          type="button"
          className={mode === "ask" ? "active" : ""}
          onClick={() => switchMode("ask")}
        >
          Soru Sor
        </button>
        <button
          type="button"
          className={mode === "compare" ? "active" : ""}
          onClick={() => switchMode("compare")}
        >
          Karşılaştır
        </button>
      </div>

      {mode === "ask" && (
        <form className="ask-form" onSubmit={handleAskSubmit}>
          <label className="field">
            <span>Üniversite (opsiyonel)</span>
            <select
              value={universityName}
              onChange={(event) => setUniversityName(event.target.value)}
            >
              <option value="">Tüm üniversiteler</option>
              {universities.map((university) => (
                <option key={university.id} value={university.name}>
                  {university.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Sorunuz</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Örn: Sosyal hayat ve ulaşım nasıl?"
              rows={3}
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Aranıyor..." : "Sor"}
          </button>
        </form>
      )}

      {mode === "compare" && (
        <form className="ask-form" onSubmit={handleCompareSubmit}>
          <div className="compare-row">
            <label className="field">
              <span>1. Üniversite</span>
              <select
                value={universityA}
                onChange={(event) => setUniversityA(event.target.value)}
              >
                <option value="">Seçiniz</option>
                {universities.map((university) => (
                  <option key={university.id} value={university.name}>
                    {university.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>2. Üniversite</span>
              <select
                value={universityB}
                onChange={(event) => setUniversityB(event.target.value)}
              >
                <option value="">Seçiniz</option>
                {universities.map((university) => (
                  <option key={university.id} value={university.name}>
                    {university.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="field">
            <span>Neye göre karşılaştıralım?</span>
            <textarea
              value={compareQuestion}
              onChange={(event) => setCompareQuestion(event.target.value)}
              placeholder="Örn: Sakin bir şehir istiyorum, sosyal hayat önemli değil. Hangisi bana daha uygun?"
              rows={3}
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Karşılaştırılıyor..." : "Karşılaştır"}
          </button>
        </form>
      )}

      {error && <p className="error">{error}</p>}

      {answer && (
        <div className="answer">
          {formatAnswer(answer)}
        </div>
      )}
    </div>
  );
}

export default App;
