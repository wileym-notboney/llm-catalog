// ABOUTME: The feed page: fetches items.json and shows one merged, filterable, chronological feed.
// ABOUTME: All display rules live in lib/feed.ts; the masthead and routing live in App.tsx.
import { useEffect, useMemo, useState } from "react";
import { Chips } from "./Chips";
import {
  KINDS,
  LABS,
  LAB_NAMES,
  filterItems,
  formatDay,
  isNew,
  itemDate,
  loadCatalog,
  readLastVisit,
  staleSources,
  timeAgo,
  type Catalog,
  type Kind,
  type Lab,
} from "./lib/feed";

export default function Feed() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lab, setLab] = useState<Lab | "all">("all");
  const [kind, setKind] = useState<Kind | "all">("all");
  // Read once, before markVisit() overwrites it, so "new" means new since the previous visit.
  const [lastVisit] = useState(readLastVisit);

  useEffect(() => {
    loadCatalog()
      .then(setCatalog)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  const shown = useMemo(
    () => (catalog ? filterItems(catalog.items, lab, kind) : []),
    [catalog, lab, kind],
  );
  const stale = catalog ? staleSources(catalog) : [];

  return (
    <>
      <p className="muted subtitle">
        Anthropic · OpenAI · Nous Research
        {catalog?.generatedAt && ` · updated ${timeAgo(catalog.generatedAt)}`}
      </p>

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
                {formatDay(itemDate(item), item.source === "anthropic-news")}
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
    </>
  );
}
