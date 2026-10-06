// ABOUTME: Feed types plus the pure helpers (filtering, "new" badge, dates) the dashboard uses.
// ABOUTME: Kept free of React so the display rules stay readable on their own.

export type Lab = "anthropic" | "openai" | "nous";
export type Kind = "news" | "changelog" | "release";

export interface Item {
  id: string;
  lab: Lab;
  kind: Kind;
  title: string;
  summary: string;
  url: string;
  publishedAt: string | null;
  source: string;
  firstSeenAt: string;
}

export interface SourceStatus {
  lastOk: string | null;
  lastError: string | null;
}

export interface Catalog {
  generatedAt: string | null;
  sources: Record<string, SourceStatus>;
  items: Item[];
}

export const LABS: Lab[] = ["anthropic", "openai", "nous"];
export const KINDS: Kind[] = ["news", "changelog", "release"];
export const LAB_NAMES: Record<Lab, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  nous: "Nous",
};

const VISIT_KEY = "llm-feed:lastVisit";

/** Sources never date some posts, so those fall back to when we first saw them. */
export function itemDate(item: Item): string {
  return item.publishedAt ?? item.firstSeenAt;
}

export function filterItems(
  items: Item[],
  lab: Lab | "all",
  kind: Kind | "all",
): Item[] {
  return items.filter(
    (item) =>
      (lab === "all" || item.lab === lab) &&
      (kind === "all" || item.kind === kind),
  );
}

export function staleSources(catalog: Catalog): string[] {
  return Object.entries(catalog.sources)
    .filter(([, status]) => status.lastError)
    .map(([id]) => id);
}

/** ISO-8601 UTC strings compare correctly as text. A first visit marks nothing as new. */
export function isNew(item: Item, lastVisit: string | null): boolean {
  return lastVisit !== null && item.firstSeenAt > lastVisit;
}

export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(
    0,
    Math.round((now - new Date(iso).getTime()) / 60000),
  );
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`;
}

export function readLastVisit(): string | null {
  try {
    return localStorage.getItem(VISIT_KEY);
  } catch {
    return null;
  }
}

export function markVisit(): void {
  try {
    localStorage.setItem(
      VISIT_KEY,
      new Date().toISOString().replace(/\.\d+Z$/, "Z"),
    );
  } catch {
    // Private mode or blocked storage: the "new" badge just stays off.
  }
}
