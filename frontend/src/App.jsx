import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

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
  const [universities, setUniversities] = useState([]);
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
    fetch(`${API_URL}/universities`)
      .then((response) => response.json())
      .then((data) => setUniversities(data))
      .catch(() => setError("Üniversite listesi yüklenemedi."));
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
