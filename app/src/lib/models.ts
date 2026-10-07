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

export function formatReviewedAt(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
