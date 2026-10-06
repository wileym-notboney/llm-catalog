// ABOUTME: The LLM feed dashboard page: fetches items.json and shows one merged, filterable feed.
// ABOUTME: Styled by theme.css (Mythological Punk); all display rules live in lib/feed.ts.
import { useEffect, useMemo, useState } from "react";
import "./theme.css";
import {
  KINDS,
  LABS,
  LAB_NAMES,
  filterItems,
  formatDay,
  isNew,
  itemDate,
  markVisit,
  readLastVisit,
  staleSources,
  timeAgo,
  type Catalog,
  type Kind,
  type Lab,
} from "./lib/feed";

function Crest() {
  return (
    <svg className="crest" viewBox="0 0 64 64" role="img" aria-label="Crest">
      <defs>
        <linearGradient id="brass" x1="0" x2="1" y1="0" y2="1">
          <stop stopColor="#d0a85e" />
          <stop offset="1" stopColor="#8c622e" />
        </linearGradient>
      </defs>
      <circle
        cx="32"
        cy="32"
        r="28"
        fill="#12161a"
        stroke="url(#brass)"
        strokeWidth="3"
      />
      <path
        d="M16 42h32M20 39h24M23 39V27h18v12M20 27h24l-12-9z"
        fill="none"
        stroke="#e7e2d8"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <path d="m33 12-5 13h5l-3 11 9-15h-5l4-9z" fill="#38a7ff" />
    </svg>
  );
}

function Chips<T extends string>(props: {
  label: string;
  options: readonly T[];
  value: T | "all";
  names?: Record<string, string>;
  onChange: (value: T | "all") => void;
}) {
  return (
    <div className="chips" role="group" aria-label={props.label}>
      {(["all", ...props.options] as const).map((option) => (
        <button
          key={option}
          type="button"
          className="chip"
          aria-pressed={props.value === option}
          onClick={() => props.onChange(option)}
        >
          {option === "all" ? "All" : (props.names?.[option] ?? option)}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lab, setLab] = useState<Lab | "all">("all");
  const [kind, setKind] = useState<Kind | "all">("all");
  // Read once, before markVisit() overwrites it, so "new" means new since the previous visit.
  const [lastVisit] = useState(readLastVisit);

  useEffect(() => {
    fetch("./items.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok)
          throw new Error(`items.json returned ${response.status}`);
        return response.json() as Promise<Catalog>;
      })
      .then(setCatalog)
      .catch((reason: Error) => setError(reason.message));
    markVisit();
  }, []);

  const shown = useMemo(
    () => (catalog ? filterItems(catalog.items, lab, kind) : []),
    [catalog, lab, kind],
  );
  const stale = catalog ? staleSources(catalog) : [];

  return (
    <main className="page">
      <header className="masthead">
        <Crest />
        <div>
          <h1>LLM Feed</h1>
          <p className="muted">
            Anthropic · OpenAI · Nous Research
            {catalog?.generatedAt &&
              ` · updated ${timeAgo(catalog.generatedAt)}`}
          </p>
        </div>
      </header>

      {stale.length > 0 && (
        <p className="banner" role="status">
          Stale: {stale.join(", ")}. Showing the last good items for these.
        </p>
      )}

      <div className="filters">
        <Chips
          label="Lab"
          options={LABS}
          value={lab}
          names={LAB_NAMES}
          onChange={setLab}
        />
        <Chips label="Kind" options={KINDS} value={kind} onChange={setKind} />
      </div>

      {error && (
        <p className="banner error" role="alert">
          Could not load the feed ({error}). Run{" "}
          <code>python3 -m feed pull</code> once.
        </p>
      )}
      {!catalog && !error && <p className="muted">Loading…</p>}
      {catalog && shown.length === 0 && (
        <p className="muted">Nothing matches these filters.</p>
      )}

      <ol className="feed">
        {shown.map((item) => (
          <li key={item.id} className={`card lab-${item.lab}`}>
            <div className="meta">
              <span className="tag">{LAB_NAMES[item.lab]}</span>
              <span className="muted">{item.kind}</span>
              <span className="muted">
                {formatDay(itemDate(item))}
                {item.publishedAt === null && " (first seen)"}
              </span>
              {isNew(item, lastVisit) && <span className="new">new</span>}
            </div>
            <h2>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.title}
              </a>
            </h2>
            {item.summary && <p className="summary">{item.summary}</p>}
          </li>
        ))}
      </ol>
    </main>
  );
}
