import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import universitiesSnapshot from "./universities.json";
import stats from "./stats.json";

// Prod'da .env.production içindeki VITE_API_URL kullanılır.
// Yoksa yerel backend'e düşer.
const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// Üniversite listesi build'e gömülü geliyor.
// Backend'den de arka planda güncel liste çekiliyor.
const CACHE_KEY = "uniguide.universities";

function readCachedUniversities() {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    const parsed = cached ? JSON.parse(cached) : null;

    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed;
    }
  } catch {
    // Cache bozuksa gömülü listeyi kullan.
  }

  return universitiesSnapshot;
}

function formatAnswer(text) {
  // **kalın** ifadeleri <strong>'a çevirir.
  const paragraphs = text.split("\n\n");

  return paragraphs.map((paragraph, pIndex) => {
    const parts = paragraph.split(/(\*\*[^\*]+\*\*)/g);

    return (
      <p key={pIndex}>
        {parts.map((part, index) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={index}>
                {part.slice(2, -2)}
              </strong>
            );
          }

          return part;
        })}
      </p>
    );
  });
}

function formatCount(value) {
  return value.toLocaleString("tr-TR");
}

/*
 * Arama için Türkçe karakterleri sadeleştiriyoruz.
 *
 * Örneğin:
 * "Boğaziçi" -> "bogazici"
 *
 * Böylece kullanıcı:
 * "bogazici"
 * yazdığında
 * "Boğaziçi Üniversitesi"
 * sonucunu bulabilir.
 */
function normalizeForSearch(text) {
  return text
    .toLocaleLowerCase("tr")
    .replace(/ğ/g, "g")
    .replace(/ü/g, "u")
    .replace(/ş/g, "s")
    .replace(/ı/g, "i")
    .replace(/ö/g, "o")
    .replace(/ç/g, "c");
}

/*
 * Native <select> yerine kullandığımız özel üniversite seçici.
 *
 * Avantajları:
 * - Her zaman aşağı doğru açılır.
 * - Arama yapılabilir.
 * - 200+ üniversite scroll edilebilir.
 * - Türkçe karakterlerle arama daha rahat.
 * - Klavyeden ArrowUp / ArrowDown / Enter / Escape desteklenir.
 */
function UniversityPicker({
  id,
  value,
  onChange,
  universities,
  allLabel,
  placeholder = "Üniversite ara..."
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const wrapperRef = useRef(null);
  const listRef = useRef(null);

  const options = useMemo(() => {
    const all = [
      ...(allLabel
        ? [
            {
              key: "__all__",
              name: allLabel,
              value: ""
            }
          ]
        : []),
      ...universities.map((university) => ({
        key: university.id,
        name: university.name,
        value: university.name
      }))
    ];

    const search = normalizeForSearch(query.trim());

    if (!search) {
      return all;
    }

    return all.filter((option) =>
      normalizeForSearch(option.name).includes(search)
    );
  }, [universities, query, allLabel]);

  // Dropdown dışına tıklanınca kapat.
  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target)
      ) {
        setOpen(false);
        setQuery("");
      }
    }

    document.addEventListener("mousedown", handlePointerDown);

    return () => {
      document.removeEventListener(
        "mousedown",
        handlePointerDown
      );
    };
  }, [open]);

  // Klavyeyle gezerken aktif seçenek görünür kalsın.
  useEffect(() => {
    if (!open || !listRef.current) {
      return;
    }

    const element = listRef.current.children[activeIndex];

    if (element) {
      element.scrollIntoView({
        block: "nearest"
      });
    }
  }, [activeIndex, open]);

  function choose(option) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
  }

  function handleKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();

      if (!open) {
        setOpen(true);
        return;
      }

      setActiveIndex((current) =>
        current + 1 >= options.length
          ? 0
          : current + 1
      );

      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();

      if (!open) {
        setOpen(true);
        return;
      }

      setActiveIndex((current) =>
        current - 1 < 0
          ? options.length - 1
          : current - 1
      );

      return;
    }

    if (event.key === "Enter" && open) {
      event.preventDefault();

      if (options[activeIndex]) {
        choose(options[activeIndex]);
      }

      return;
    }

    if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div className="picker" ref={wrapperRef}>
      <input
        id={id}
        type="text"
        className="picker-input"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        autoComplete="off"
        value={
          open
            ? query
            : value || placeholder
        }
        placeholder={placeholder}
        onFocus={() => {
          setOpen(true);
          setActiveIndex(0);
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setActiveIndex(0);
          setOpen(true);
        }}
        onKeyDown={handleKeyDown}
      />

      <button
        type="button"
        className="picker-arrow"
        aria-label="Üniversite listesini aç"
        onMouseDown={(event) => {
          event.preventDefault();
        }}
        onClick={() => {
          setOpen((current) => !current);
          setQuery("");
        }}
      >
        <span className={open ? "arrow open" : "arrow"}>
          ⌄
        </span>
      </button>

      {open && (
        <div className="picker-dropdown">
          <div className="picker-search">
            <span>⌕</span>

            <input
              type="text"
              value={query}
              autoFocus
              placeholder="Üniversite ara..."
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={handleKeyDown}
            />
          </div>

          <ul
            className="picker-list"
            ref={listRef}
            role="listbox"
          >
            {options.length === 0 ? (
              <li className="picker-empty">
                Eşleşen üniversite bulunamadı
              </li>
            ) : (
              options.map((option, index) => (
                <li
                  key={option.key}
                  role="option"
                  aria-selected={
                    option.value === value
                  }
                  className={
                    index === activeIndex
                      ? "active"
                      : ""
                  }
                  onMouseEnter={() =>
                    setActiveIndex(index)
                  }
                  onMouseDown={(event) => {
                    event.preventDefault();
                  }}
                  onClick={() => choose(option)}
                >
                  {option.name}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function AboutSection() {
  // Sayılar stats.json'dan geliyor.
  const [year, month, day] =
    stats.updatedAt.split("-");

  return (
    <details className="about">
      <summary>
        Asistanımız nasıl çalışıyor?
      </summary>

      <div className="about-body">
        <p>
          Bu asistan, öğrencilerin internette
          paylaştığı{" "}
          <strong>
            {formatCount(stats.totalReviews)} gerçek
            yorumu
          </strong>{" "}
          topladı. {stats.totalUniversities} üniversitenin{" "}
          {stats.universitiesCovered}'inde en az bir
          yorum var.
        </p>

        <ul className="about-sources">
          {stats.sources.map((source) => (
            <li key={source.label}>
              {source.label}
              <span>
                {formatCount(source.count)}
              </span>
            </li>
          ))}
        </ul>

        <p>
          Bir soru sorduğunda, soruyla en ilgili
          yorumlar bulunur ve cevap{" "}
          <strong>
            yalnızca o yorumlara dayanılarak
          </strong>{" "}
          yazılır. Yorumlarda geçmeyen bilgi eklenmez;
          eldeki yorumlar soruyu cevaplamaya yetmiyorsa
          asistan bunu açıkça söyler.
        </p>

        <p className="about-caveat">
          <strong>Dikkat:</strong> Bu yorumlar
          öğrencilerin kişisel görüşleridir, resmî bilgi
          değildir. Farklı tarihlerde yazıldıkları için
          güncelliğini yitirmiş olabilirler ve bazı
          üniversitelerde yorum sayısı azdır. Tercih
          kararını verirken tek kaynak olarak kullanma.
        </p>

        <p className="about-updated">
          Veriler son güncelleme: {day}.{month}.{year}
        </p>
      </div>
    </details>
  );
}

function App() {
  const [universities, setUniversities] =
    useState(readCachedUniversities);

  const [mode, setMode] = useState("ask");

  // Tek soru modu
  const [universityName, setUniversityName] =
    useState("");

  const [question, setQuestion] =
    useState("");

  // Karşılaştırma modu
  const [universityA, setUniversityA] =
    useState("");

  const [universityB, setUniversityB] =
    useState("");

  const [compareQuestion, setCompareQuestion] =
    useState("");

  const [answer, setAnswer] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState(null);

  // Üniversiteleri backend'den arka planda güncelle.
  useEffect(() => {
    let cancelled = false;

    async function refreshUniversities(
      attempt = 0
    ) {
      try {
        const response = await fetch(
          `${API_URL}/universities`
        );

        if (!response.ok) {
          throw new Error("Sunucu hatası");
        }

        const data = await response.json();

        if (
          cancelled ||
          !Array.isArray(data) ||
          data.length === 0
        ) {
          return;
        }

        setUniversities(data);

        try {
          localStorage.setItem(
            CACHE_KEY,
            JSON.stringify(data)
          );
        } catch {
          // Storage kullanılamıyorsa sorun değil.
        }
      } catch {
        if (!cancelled && attempt < 12) {
          setTimeout(
            () =>
              refreshUniversities(
                attempt + 1
              ),
            15000
          );
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
      const response = await fetch(
        `${API_URL}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            question,
            university_name:
              universityName || null
          })
        }
      );

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

    if (
      !compareQuestion.trim() ||
      !universityA ||
      !universityB
    ) {
      return;
    }

    if (universityA === universityB) {
      setError(
        "Karşılaştırmak için iki farklı üniversite seç."
      );
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const response = await fetch(
        `${API_URL}/compare`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            question: compareQuestion,
            university_names: [
              universityA,
              universityB
            ]
          })
        }
      );

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

        <p>
          Gerçek öğrenci yorumlarına dayalı
          üniversite asistanı
        </p>
      </header>

      <AboutSection />

      <div className="mode-tabs">
        <button
          type="button"
          className={
            mode === "ask" ? "active" : ""
          }
          onClick={() => switchMode("ask")}
        >
          Soru Sor
        </button>

        <button
          type="button"
          className={
            mode === "compare" ? "active" : ""
          }
          onClick={() => switchMode("compare")}
        >
          Karşılaştır
        </button>
      </div>

      {mode === "ask" && (
        <form
          className="ask-form"
          onSubmit={handleAskSubmit}
        >
          <div className="field">
            <span>
              Üniversite (opsiyonel)
            </span>

            <UniversityPicker
              id="ask-university"
              value={universityName}
              onChange={setUniversityName}
              universities={universities}
              allLabel="Tüm üniversiteler"
              placeholder="Tüm üniversiteler"
            />
          </div>

          <label className="field">
            <span>Sorunuz</span>

            <textarea
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="Örn: Sosyal hayat ve ulaşım nasıl?"
              rows={3}
            />
          </label>

          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Aranıyor..."
              : "Sor"}
          </button>
        </form>
      )}

      {mode === "compare" && (
        <form
          className="ask-form"
          onSubmit={handleCompareSubmit}
        >
          <div className="compare-row">
            <div className="field">
              <span>1. Üniversite</span>

              <UniversityPicker
                id="compare-1"
                value={universityA}
                onChange={setUniversityA}
                universities={universities}
                placeholder="Üniversite seç..."
              />
            </div>

            <div className="field">
              <span>2. Üniversite</span>

              <UniversityPicker
                id="compare-2"
                value={universityB}
                onChange={setUniversityB}
                universities={universities}
                placeholder="Üniversite seç..."
              />
            </div>
          </div>

          <label className="field">
            <span>
              Neye göre karşılaştıralım?
            </span>

            <textarea
              value={compareQuestion}
              onChange={(event) =>
                setCompareQuestion(
                  event.target.value
                )
              }
              placeholder="Örn: Sakin bir şehir istiyorum, sosyal hayat önemli değil. Hangisi bana daha uygun?"
              rows={3}
            />
          </label>

          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Karşılaştırılıyor..."
              : "Karşılaştır"}
          </button>
        </form>
      )}

      {error && (
        <p className="error">
          {error}
        </p>
      )}

      {answer && (
        <div className="answer">
          {formatAnswer(answer)}
        </div>
      )}
    </div>
  );
}

export default App;