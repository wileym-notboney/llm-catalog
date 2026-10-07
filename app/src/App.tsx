// ABOUTME: The shell: masthead, crest, nav, and the hash route that picks the feed or the catalog.
// ABOUTME: Routes are "#/" (feed) and "#/models" (catalog); anything else falls back to the feed.
import { useEffect, useState } from "react";
import "./theme.css";
import Feed from "./Feed";
import Models from "./Models";

const PAGES = [
  { hash: "#/", label: "Feed" },
  { hash: "#/models", label: "Models" },
] as const;

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

/** The hash is the only router: no dependency, and the single static file still answers every link. */
function useHash(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const read = () => setHash(window.location.hash);
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const onModels = hash === "#/models";

  return (
    <main className="page">
      <header className="masthead">
        <Crest />
        <div>
          <h1>LLM Feed</h1>
          <nav className="nav" aria-label="Pages">
            {PAGES.map((page) => (
              <a
                key={page.hash}
                className="chip"
                href={page.hash}
                aria-current={
                  (page.hash === "#/models") === onModels ? "page" : undefined
                }
              >
                {page.label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      {onModels ? <Models /> : <Feed />}
    </main>
  );
}
