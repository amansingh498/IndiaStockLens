import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertCircle,
  Building2,
  CheckCircle2,
  IndianRupee,
  Loader2,
  Search,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function App() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyze(event) {
    event.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;

    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/analyze/${encodeURIComponent(symbol)}`);
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }
      setAnalysis(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to analyze ticker");
    } finally {
      setLoading(false);
    }
  }

  const sourceCounts = useMemo(() => {
    const values = Object.values(analysis?.sources || {});
    return {
      ok: values.filter((source) => source.status === "ok").length,
      warning: values.filter((source) => source.status !== "ok").length,
      total: values.length,
    };
  }, [analysis]);

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">IndiaStockLens</p>
            <h1>Stock due diligence brief</h1>
          </div>
          <form className="searchbar" onSubmit={analyze}>
            <Search size={18} aria-hidden="true" />
            <input
              aria-label="Ticker"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="RELIANCE"
            />
            <button disabled={loading} type="submit">
              {loading ? <Loader2 className="spin" size={18} /> : <Activity size={18} />}
              Analyze
            </button>
          </form>
        </header>

        {error ? (
          <div className="notice error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        {analysis ? (
          <div className="dashboard">
            <section className="summary-band">
              <div className="identity">
                <div className="mark">
                  <Building2 size={26} />
                </div>
                <div>
                  <p className="muted">{analysis.price?.exchange || "NSE/BSE"}</p>
                  <h2>{analysis.price?.name || analysis.company || analysis.ticker}</h2>
                  <p className="muted">
                    Updated {new Date(analysis.as_of).toLocaleString("en-IN")}
                  </p>
                </div>
              </div>
              <ScoreGauge score={analysis.scores.overall} label={analysis.scores.label} />
            </section>

            <section className="metrics-grid">
              <Metric
                icon={<IndianRupee size={20} />}
                label="Live price"
                value={formatCurrency(analysis.price)}
                detail={formatMove(analysis.price)}
                tone={Number(analysis.price?.change_percent) >= 0 ? "up" : "down"}
              />
              <Metric
                icon={<TrendingUp size={20} />}
                label="Analyst target"
                value={formatNumber(analysis.price?.analyst_target)}
                detail={formatRecommendation(analysis.price?.recommendation)}
              />
              <Metric
                icon={<ShieldAlert size={20} />}
                label="Regulatory risk"
                value={`${analysis.scores.regulatory_risk}/10`}
                detail={`${analysis.regulatory.length} active item(s)`}
              />
              <Metric
                icon={<CheckCircle2 size={20} />}
                label="Sources"
                value={`${sourceCounts.ok}/${sourceCounts.total}`}
                detail={`${sourceCounts.warning} warning(s)`}
              />
            </section>

            <section className="content-grid">
              <article className="brief-panel">
                <h3>Plain-English Brief</h3>
                <p>{analysis.brief}</p>
              </article>

              <article className="score-panel">
                <h3>Scored Dimensions</h3>
                <ScoreRow label="Fundamentals" value={analysis.scores.fundamentals} />
                <ScoreRow label="Technicals" value={analysis.scores.technicals} />
                <ScoreRow label="Sentiment" value={analysis.scores.sentiment} />
                <ScoreRow label="Regulatory risk" value={analysis.scores.regulatory_risk} />
                <ScoreRow label="Institutional trust" value={analysis.scores.institutional_trust} />
              </article>
            </section>

            <section className="source-table">
              <div className="section-heading">
                <h3>Source Status</h3>
                <p>Live data failures stay visible without blocking the brief.</p>
              </div>
              <div className="sources">
                {Object.entries(analysis.sources).map(([name, source]) => (
                  <SourceItem key={name} name={name} source={source} />
                ))}
              </div>
            </section>
          </div>
        ) : (
          <section className="empty-state">
            <h2>Enter an NSE ticker to generate the first brief.</h2>
            <p>The backend currently normalizes Yahoo Finance quote data and reports unavailable sources explicitly.</p>
          </section>
        )}
      </section>
    </main>
  );
}

function ScoreGauge({ score, label }) {
  return (
    <div className="score-gauge" style={{ "--score": `${score}%` }}>
      <div>
        <span>{score}</span>
        <small>/100</small>
      </div>
      <p>{label}</p>
    </div>
  );
}

function Metric({ icon, label, value, detail, tone }) {
  return (
    <article className={`metric ${tone || ""}`}>
      <div className="metric-icon">{icon}</div>
      <p>{label}</p>
      <strong>{value || "Unavailable"}</strong>
      <span>{detail || "No detail"}</span>
    </article>
  );
}

function ScoreRow({ label, value }) {
  return (
    <div className="score-row">
      <span>{label}</span>
      <div className="bar" aria-hidden="true">
        <i style={{ width: `${value * 10}%` }} />
      </div>
      <strong>{value}/10</strong>
    </div>
  );
}

function SourceItem({ name, source }) {
  const ok = source.status === "ok";
  return (
    <article className={`source-item ${ok ? "ok" : "warn"}`}>
      <div>
        {ok ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
        <strong>{name.replaceAll("_", " ")}</strong>
      </div>
      <span>{source.status}</span>
      {source.error ? <p>{source.error}</p> : null}
    </article>
  );
}

function formatCurrency(price) {
  if (!price?.current) return "";
  return `${price.currency || "INR"} ${Number(price.current).toLocaleString("en-IN")}`;
}

function formatMove(price) {
  if (price?.change_percent === null || price?.change_percent === undefined) return "";
  const value = Number(price.change_percent);
  const Icon = value >= 0 ? TrendingUp : TrendingDown;
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}% ${Icon ? "" : ""}`;
}

function formatNumber(value) {
  if (value === null || value === undefined) return "";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function formatRecommendation(value) {
  if (!value) return "No recommendation";
  return String(value).replaceAll("_", " ");
}

createRoot(document.getElementById("root")).render(<App />);
