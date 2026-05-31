import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertCircle,
  BarChart3,
  Building2,
  CalendarDays,
  CheckCircle2,
  Database,
  ExternalLink,
  Gauge,
  IndianRupee,
  Loader2,
  Newspaper,
  PanelTop,
  ScrollText,
  Search,
  ShieldCheck,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import "./styles.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const QUICK_TICKERS = ["RELIANCE", "TCS", "INFY", "HDFCBANK"];
const REQUEST_TIMEOUT_MS = 120000;

function App() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyze(event) {
    event.preventDefault();
    await runAnalyze(ticker);
  }

  async function runAnalyze(value) {
    const symbol = value.trim().toUpperCase();
    if (!symbol) return;

    setLoading(true);
    setError("");
    setTicker(symbol);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const endpoint = `${API_BASE}/analyze/${encodeURIComponent(symbol)}`;
      const response = await fetch(endpoint, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`Backend returned ${response.status} from ${endpoint}`);
      }
      setAnalysis(normalizeAnalysis(await response.json()));
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Backend took too long to respond. Try the same ticker again; Render or Anakin may still be warming up.");
      } else {
        setError(err instanceof Error ? err.message : "Unable to analyze ticker");
      }
    } finally {
      window.clearTimeout(timeout);
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

  const watchItems = useMemo(() => buildWatchItems(analysis), [analysis]);

  return (
    <main className="app-shell">
      <section className="workspace">
        <nav className="menubar" aria-label="Primary">
          <div className="brand-lockup">
            <div className="brand-mark">
              <BarChart3 size={20} />
            </div>
            <div>
              <strong>IndiaStockLens</strong>
              <span>Live equity intelligence</span>
            </div>
          </div>
          <div className="menu-links">
            <a href="#overview">
              <Gauge size={16} />
              Overview
            </a>
            <a href="#reports">
              <ScrollText size={16} />
              Reports
            </a>
            <a href="#sources">
              <Database size={16} />
              Sources
            </a>
          </div>
        </nav>

        <header className="topbar">
          <div className="hero-copy">
            <p className="eyebrow">IndiaStockLens</p>
            <h1>Live Indian Stock Analysis</h1>
            <p className="hero-subtitle">
              Fast quote, risk, report, and source checks for Indian equities.
            </p>
            <div className="quick-tickers" aria-label="Popular tickers">
              {QUICK_TICKERS.map((symbol) => (
                <button
                  key={symbol}
                  type="button"
                  onClick={() => runAnalyze(symbol)}
                  disabled={loading}
                  className={ticker === symbol ? "active" : ""}
                >
                  {symbol}
                </button>
              ))}
            </div>
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

        {loading && !analysis ? <LoadingState /> : null}

        {analysis ? (
          <div className="dashboard">
            {loading ? (
              <div className="notice loading">
                <Loader2 className="spin" size={18} />
                <span>Refreshing {ticker}</span>
              </div>
            ) : null}
            <section className="summary-band" id="overview">
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

            <SourceHealthBanner analysis={analysis} sourceCounts={sourceCounts} />

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
              <article className="brief-panel insight-panel">
                <div className="panel-title">
                  <Activity size={18} />
                  <h3>Stock Insight</h3>
                </div>
                <p>{analysis.brief}</p>
              </article>

              <WatchPanel items={watchItems} />
            </section>

            <section className="content-grid secondary-content">
              <article className="score-panel">
                <div className="panel-title">
                  <TrendingUp size={18} />
                  <h3>Score Breakdown</h3>
                </div>
                <p className="score-section-label">Primary signals</p>
                <ScoreRow label="Data confidence" value={analysis.scores.data_confidence} primary />
                <ScoreRow label="Investment quality" value={analysis.scores.investment_attractiveness} primary />
                <ScoreRow label="Regulatory safety" value={analysis.scores.regulatory_risk} primary />
                <p className="score-section-label supporting">Supporting detail</p>
                <ScoreRow label="Fundamentals" value={analysis.scores.fundamentals} />
                <ScoreRow label="Technicals" value={analysis.scores.technicals} />
                <ScoreRow label="Sentiment" value={analysis.scores.sentiment} />
                <ScoreRow label="Institutional trust" value={analysis.scores.institutional_trust} />
                <ScoreGuide />
              </article>
              <QuotePanel price={analysis.price} />
            </section>

            <section className="detail-grid" id="reports">
              <ItemPanel
                title="Company Reports & Events"
                icon={<ScrollText size={18} />}
                items={analysis.filings}
                empty="No matching company reports or events returned."
              />
            </section>

            <section className="detail-grid regulatory-grid">
              <ItemPanel
                title="Regulatory Watch"
                icon={<ShieldAlert size={18} />}
                items={analysis.regulatory}
                empty="No matching SEBI items returned."
              />
              <ItemPanel
                title="Latest News"
                icon={<Newspaper size={18} />}
                items={analysis.news}
                empty="News sources are not enabled in the default low-credit profile."
              />
            </section>

            <section className="source-table" id="sources">
              <div className="section-heading">
                <h3>Sources</h3>
                <p>Provenance for the quote, reports, and risk signals shown above.</p>
              </div>
              <div className="sources">
                {Object.entries(analysis.sources).map(([name, source]) => (
                  <SourceItem key={name} name={name} source={source} />
                ))}
              </div>
            </section>
          </div>
        ) : (
          !loading && (
          <section className="empty-state">
            <div className="empty-visual">
              <PanelTop size={28} />
            </div>
            <div>
              <h2>Enter an NSE ticker to generate the first brief.</h2>
              <p>Use the search above or start with one of the liquid large-cap names.</p>
            </div>
          </section>
          )
        )}
      </section>
    </main>
  );
}

function SourceHealthBanner({ analysis, sourceCounts }) {
  const warningSources = Object.entries(analysis.sources || {}).filter(([, source]) => source.status !== "ok");
  const isHealthy = sourceCounts.warning === 0 && sourceCounts.total > 0;
  return (
    <section className={`source-health ${isHealthy ? "healthy" : "degraded"}`}>
      <div>
        {isHealthy ? <ShieldCheck size={20} /> : <AlertCircle size={20} />}
        <strong>{sourceCounts.ok}/{sourceCounts.total} live sources available</strong>
      </div>
      <p>
        {isHealthy
          ? "All configured sources returned usable data for this brief."
          : `${warningSources.map(([name]) => name.replaceAll("_", " ")).join(", ")} need review.`}
      </p>
    </section>
  );
}

function WatchPanel({ items }) {
  return (
    <article className="watch-panel">
      <div className="panel-title">
        <ShieldAlert size={18} />
        <h3>What To Watch</h3>
        <span>{items.length}</span>
      </div>
      <div className="watch-list">
        {items.map((item) => (
          <div key={item.title} className={`watch-item ${item.tone}`}>
            <strong>{item.title}</strong>
            <p>{item.detail}</p>
          </div>
        ))}
      </div>
    </article>
  );
}

function buildWatchItems(analysis) {
  if (!analysis) return [];
  const items = [];
  const scores = analysis.scores || {};
  const sources = analysis.sources || {};
  const failedSources = Object.entries(sources).filter(([, source]) => source.status !== "ok");

  if (failedSources.length) {
    items.push({
      tone: "warn",
      title: "Data coverage is incomplete",
      detail: `${failedSources.map(([name]) => name.replaceAll("_", " ")).join(", ")} did not return cleanly.`,
    });
  }

  if ((scores.data_confidence ?? 0) < 6) {
    items.push({
      tone: "warn",
      title: "Low data confidence",
      detail: "Treat the score as preliminary until more live sources return usable records.",
    });
  }

  if ((scores.regulatory_risk ?? 10) < 6) {
    items.push({
      tone: "risk",
      title: "Regulatory review needed",
      detail: "Regulatory safety is below the preferred range or source coverage is weak.",
    });
  }

  if ((scores.investment_attractiveness ?? 0) < 6) {
    items.push({
      tone: "neutral",
      title: "Investment quality is not strong yet",
      detail: "Valuation, ownership, analyst, or fundamentals signals are not compelling enough.",
    });
  }

  if (!analysis.price?.current) {
    items.push({
      tone: "risk",
      title: "Live quote missing",
      detail: "Price-based metrics and technical movement may be unavailable or stale.",
    });
  }

  if (!items.length) {
    items.push({
      tone: "ok",
      title: "No major watch item",
      detail: "The available live data does not show an obvious dashboard-level concern.",
    });
  }

  return items.slice(0, 4);
}

function normalizeAnalysis(payload) {
  const scores = payload?.scores || {};
  const fundamentals = safeScore(scores.fundamentals, 5);
  const technicals = safeScore(scores.technicals, 4);
  const sentiment = safeScore(scores.sentiment, 5);
  const regulatoryRisk = safeScore(scores.regulatory_risk, 6);
  const institutionalTrust = safeScore(scores.institutional_trust, 5);
  const dataConfidence = safeScore(scores.data_confidence, Math.min(10, 2 + Object.values(payload?.sources || {}).filter((source) => source?.status === "ok").length * 2));
  const investmentAttractiveness = safeScore(scores.investment_attractiveness, Math.round((fundamentals + institutionalTrust) / 2));
  const overall = Number.isFinite(Number(scores.overall))
    ? Number(scores.overall)
    : Math.max(0, Math.min(100, Math.round(dataConfidence * 2 + investmentAttractiveness * 5 + regulatoryRisk * 3)));

  return {
    ...payload,
    price: payload?.price || {},
    news: Array.isArray(payload?.news) ? payload.news : [],
    filings: Array.isArray(payload?.filings) ? payload.filings : [],
    regulatory: Array.isArray(payload?.regulatory) ? payload.regulatory : [],
    sources: payload?.sources || {},
    scores: {
      ...scores,
      data_confidence: dataConfidence,
      investment_attractiveness: investmentAttractiveness,
      regulatory_risk: regulatoryRisk,
      fundamentals,
      technicals,
      sentiment,
      institutional_trust: institutionalTrust,
      overall,
      label: scores.label || (overall >= 75 ? "Strong" : overall >= 55 ? "Watch" : "Caution"),
    },
    brief: payload?.brief || "Analysis returned without a generated brief.",
  };
}

function safeScore(value, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.max(0, Math.min(10, Math.round(numeric)));
}

function LoadingState() {
  return (
    <section className="loading-state" aria-live="polite">
      <div className="loading-card">
        <Loader2 className="spin" size={24} />
        <div>
          <h2>Building live brief</h2>
          <p>Quote, company events, regulatory watch, and source provenance are loading.</p>
        </div>
      </div>
      <div className="skeleton-grid">
        <span />
        <span />
        <span />
        <span />
      </div>
    </section>
  );
}

function ScoreGuide() {
  const rows = [
    ["Overall score", "0-100 blend of data confidence, investment quality, and regulatory safety."],
    ["Data confidence", "How much usable live data was returned by the connected sources."],
    ["Investment quality", "Valuation, analyst stance, ownership, and available fundamental signals."],
    ["Regulatory safety", "Higher means fewer visible SEBI/NSE risk signals in returned data."],
    ["Fundamentals", "Price and company financial signals such as PE, filings, and quarterly data."],
    ["Technicals", "Short-term price movement from the latest quote snapshot."],
  ];

  return (
    <div className="score-guide">
      {rows.map(([term, meaning]) => (
        <div key={term}>
          <strong>{term}</strong>
          <span>{meaning}</span>
        </div>
      ))}
    </div>
  );
}

function QuotePanel({ price }) {
  const rows = [
    ["Open", formatNumber(price?.open)],
    ["Previous close", formatNumber(price?.previous_close)],
    ["Day high", formatNumber(price?.day_high)],
    ["Day low", formatNumber(price?.day_low)],
    ["Volume", formatNumber(price?.volume)],
    ["Market cap", formatNumber(price?.market_cap)],
    ["PE", formatNumber(price?.pe_ratio)],
    ["Forward PE", formatNumber(price?.forward_pe)],
    ["EPS", formatNumber(price?.eps)],
    ["Beta", formatNumber(price?.beta)],
    ["Book value", formatNumber(price?.book_value)],
    ["Price/book", formatNumber(price?.price_to_book)],
  ].filter(([, value]) => value);

  return (
    <article className="data-panel">
      <div className="panel-title">
        <IndianRupee size={18} />
        <h3>Quote Snapshot</h3>
      </div>
      {rows.length ? (
        <dl className="quote-list">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="empty-copy">No quote details returned.</p>
      )}
    </article>
  );
}

function ItemPanel({ title, icon, items, empty }) {
  const visibleItems = Array.isArray(items) ? items.slice(0, 8) : [];
  return (
    <article className="data-panel">
      <div className="panel-title">
        {icon}
        <h3>{title}</h3>
        <span>{visibleItems.length}</span>
      </div>
      {visibleItems.length ? (
        <div className="item-list">
          {visibleItems.map((item, index) => (
            <DataItem key={item.url || item.link || item.xbrl_link || `${title}-${index}`} item={item} />
          ))}
        </div>
      ) : (
        <p className="empty-copy">{empty}</p>
      )}
    </article>
  );
}

function DataItem({ item }) {
  const title =
    item.title ||
    item.headline ||
    item.subject ||
    item.purpose ||
    item.type ||
    item.company ||
    item.name ||
    "Untitled item";
  const date = item.date || item.published || item.filing_date || item.from_date;
  const href = item.link || item.url || item.xbrl_link;
  const tags = Array.isArray(item.tags) ? item.tags : [];

  return (
    <article className="data-item">
      <div className="item-topline">
        <span>{item.source || item.category || "source"}</span>
        {item.severity ? <span className={`severity severity-${item.severity}`}>{item.severity}</span> : null}
        {date ? (
          <small>
            <CalendarDays size={13} />
            {date}
          </small>
        ) : null}
      </div>
      <strong>{title}</strong>
      {item.detail ? <p className="item-detail">{item.detail}</p> : null}
      <div className="item-meta">
        {item.symbol ? <span>{item.symbol}</span> : null}
        {item.quarter ? <span>{item.quarter}</span> : null}
        {item.period ? <span>{item.period}</span> : null}
        {item.financial_year ? <span>{item.financial_year}</span> : null}
        {tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer">
          <ExternalLink size={14} />
          Open
        </a>
      ) : null}
    </article>
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

function ScoreRow({ label, value, primary }) {
  return (
    <div className={`score-row${primary ? " score-row--primary" : ""}`}>
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
  const keys = Array.isArray(source.data?.keys) ? source.data.keys : [];
  const counts = source.data?.counts && typeof source.data.counts === "object" ? source.data.counts : {};
  const partialErrors = Array.isArray(source.data?.partial_errors) ? source.data.partial_errors : [];
  const countText = Object.entries(counts)
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");
  return (
    <article className={`source-item ${ok ? "ok" : "warn"}`}>
      <div>
        {ok ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
        <strong>{name.replaceAll("_", " ")}</strong>
      </div>
      <span>{source.status}</span>
      {keys.length ? <p>{keys.join(", ")}</p> : null}
      {countText ? <p>{countText}</p> : null}
      {partialErrors.map((partialError) => (
        <p key={partialError} className="source-error">{partialError}</p>
      ))}
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
