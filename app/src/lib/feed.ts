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

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value));
}

/** Check the JSON boundary before rendering: TypeScript casts cannot validate a response. */
export function validateCatalog(value: unknown): asserts value is Catalog {
  const invalid = () => { throw new Error("items.json has an invalid catalog shape"); };
  if (!isRecord(value) || !isRecord(value.sources) || !Array.isArray(value.items)) {
    return invalid();
  }
  if (value.generatedAt != null && !isTimestamp(value.generatedAt)) invalid();
  for (const status of Object.values(value.sources)) {
    if (!isRecord(status) ||
      (status.lastOk != null && !isTimestamp(status.lastOk)) ||
      (status.lastError != null && typeof status.lastError !== "string")) invalid();
  }
  for (const item of value.items) {
    if (!isRecord(item)) return invalid();
    if (!["id", "lab", "kind", "title", "summary", "url", "source"].every(
      (key) => typeof item[key] === "string",
    ) || !LABS.includes(item.lab as Lab) || !KINDS.includes(item.kind as Kind) ||
      !/^https?:\/\//i.test(item.url as string) || !isTimestamp(item.firstSeenAt) ||
      (item.publishedAt !== null && !isTimestamp(item.publishedAt))) invalid();
  }
}

/** A failed load is not a visit. Use the request start so later arrivals stay new. */
export async function loadCatalog(): Promise<Catalog> {
  const visitStarted = new Date();
  const response = await fetch("./items.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`items.json returned ${response.status}`);
  const catalog: unknown = await response.json();
  validateCatalog(catalog);
  markVisit(visitStarted);
  return catalog;
}

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

export function formatDay(iso: string, dateOnly = false): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: dateOnly ? "UTC" : undefined,
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

export function markVisit(visitedAt: Date = new Date()): void {
  try {
    localStorage.setItem(
      VISIT_KEY,
      visitedAt.toISOString().replace(/\.\d+Z$/, "Z"),
    );
  } catch {
    // Private mode or blocked storage: the "new" badge just stays off.
  }
}
