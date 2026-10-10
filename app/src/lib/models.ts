// ABOUTME: Model catalog types plus the pure helpers (provider filter, ordering) the page uses.
// ABOUTME: Kept free of React, like lib/feed.ts; the data itself is the committed models.json.
import catalog from "../models.json";

export type Provider = "anthropic" | "openai" | "ollama";

export interface Model {
  id: string;
  name: string;
  provider: Provider;
  role: string;
  context: string;
  /** Token pricing for hosted models; null for local ones, where it does not apply. */
  price: string | null;
  /** Parameter sizes and the pull command for local models; null for hosted ones. */
  size: string | null;
  strengths: string[];
  weaknesses: string[];
  docs: string;
}

export interface ModelCatalog {
  reviewedAt: string;
  models: Model[];
}

export const MODEL_CATALOG = catalog as ModelCatalog;

export const PROVIDERS: Provider[] = ["anthropic", "openai", "ollama"];
export const PROVIDER_NAMES: Record<Provider, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  ollama: "Ollama (local)",
};

export function filterModels(
  models: Model[],
  provider: Provider | "all",
): Model[] {
  return models.filter(
    (model) => provider === "all" || model.provider === provider,
  );
}

/**
 * Groups the models by provider in PROVIDERS order, keeping each provider's curated
 * order (roughly strongest first) within its group. Grouping is the one ordering that
 * survives edits to models.json, and it keeps the hosted providers together with the
 * local models last, since "can I run this at all?" is the first question a reader has.
 *
 * Sorts a copy: `models` is the shared catalog array when nothing is filtered out.
 */
export function orderModels(models: Model[]): Model[] {
  return [...models].sort(
    (left, right) =>
      PROVIDERS.indexOf(left.provider) - PROVIDERS.indexOf(right.provider),
  );
}

/** Only the specs that apply to a given model: hosted ones price, local ones size. */
export function specsOf(model: Model): string[] {
  return [model.context, model.price, model.size].filter(
    (spec): spec is string => spec !== null,
  );
}

/** A hosted model is priced per token; a local one has a parameter size instead. */
export function isHosted(model: Model): boolean {
  return model.price !== null;
}

export type Host = "all" | "hosted" | "local";

export function filterByHost(models: Model[], host: Host): Model[] {
  if (host === "all") return models;
  return models.filter((model) =>
    host === "hosted" ? isHosted(model) : !isHosted(model),
  );
}

export type Sort = "catalog" | "name" | "context" | "price";

export const SORTS: Sort[] = ["catalog", "name", "context", "price"];
export const SORT_NAMES: Record<Sort, string> = {
  catalog: "Editor's order",
  name: "Name",
  context: "Context",
  price: "Price",
};

/**
 * Reads the leading magnitude out of a free-form spec string: "1M tokens" -> 1_000_000,
 * "200K tokens, 64K output" -> 200_000, "$4 / $20 per MTok" -> 4. Returns NaN when there
 * is no number, so callers can decide where the unparseable ones land.
 */
export function parseMagnitude(text: string | null): number {
  if (text === null) return NaN;
  const match = text.match(/\$?\s*([\d.]+)\s*([KMB])?/i);
  if (!match) return NaN;
  const scale = { k: 1e3, m: 1e6, b: 1e9 }[match[2]?.toLowerCase() ?? ""] ?? 1;
  return Number(match[1]) * scale;
}

/**
 * Sort key for the "biggest context" ranking: a larger window sorts earlier (1M at the
 * top), and an unparseable context (NaN) sorts last. Negating the size flips the ascending
 * sort to descending; Infinity for NaN parks the unrankable ones at the bottom.
 */
export function contextKey(model: Model): number {
  const size = parseMagnitude(model.context);
  return Number.isNaN(size) ? Infinity : -size;
}

/**
 * Sort key for the "cheapest first" ranking. Price strings read "$4 / $20 per MTok", so
 * parseMagnitude(model.price) grabs the input price — the natural thing to rank on. Local
 * models have no token price (price === null, so NaN); mapping NaN to Infinity sorts them
 * last, after every priced model.
 */
export function priceKey(model: Model): number {
  const price = parseMagnitude(model.price);
  return Number.isNaN(price) ? Infinity : price;
}

export function sortModels(models: Model[], sort: Sort): Model[] {
  if (sort === "catalog") return orderModels(models);
  const key: (model: Model) => number | string =
    sort === "name"
      ? (model) => model.name
      : sort === "context"
        ? contextKey
        : priceKey;
  return [...models].sort((left, right) => {
    const a = key(left);
    const b = key(right);
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

export function formatReviewedAt(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
