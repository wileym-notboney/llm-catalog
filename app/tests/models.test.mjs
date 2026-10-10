// Offline checks for the model catalog helpers: magnitude parsing, host filter, sorting.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

// Reuse the installed compiler so the tests need no new dependency or generated files.
// Drop the models.json import and its one consumer: a data: URL module can't resolve a
// relative JSON path, and these tests exercise the pure helpers against their own fixtures.
const source = readFileSync(
  new URL("../src/lib/models.ts", import.meta.url),
  "utf8",
)
  .replace(/^import catalog .*$/m, "")
  .replace(/^export const MODEL_CATALOG .*$/m, "");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2023,
    module: ts.ModuleKind.ESNext,
  },
});
const lib = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const { parseMagnitude, isHosted, filterByHost, sortModels } = lib;

const hosted = (id, name, context, price) => ({
  id,
  name,
  provider: "anthropic",
  role: "",
  context,
  price,
  size: null,
  strengths: [],
  weaknesses: [],
  docs: "",
});
const local = (id, name, context) => ({
  id,
  name,
  provider: "ollama",
  role: "",
  context,
  price: null,
  size: "8B",
  strengths: [],
  weaknesses: [],
  docs: "",
});

test("parseMagnitude reads leading number and K/M/B suffix", () => {
  assert.equal(parseMagnitude("1M tokens, 128K output"), 1_000_000);
  assert.equal(parseMagnitude("200K tokens"), 200_000);
  assert.equal(parseMagnitude("$4 / $20 per MTok"), 4);
  assert.equal(parseMagnitude("$0.20 cache reads"), 0.2);
  assert.ok(Number.isNaN(parseMagnitude(null)));
  assert.ok(Number.isNaN(parseMagnitude("no digits here")));
});

test("isHosted / filterByHost split priced from local models", () => {
  const models = [hosted("a", "A", "1M", "$2 / $10"), local("b", "B", "128K")];
  assert.equal(isHosted(models[0]), true);
  assert.equal(isHosted(models[1]), false);
  assert.deepEqual(
    filterByHost(models, "hosted").map((m) => m.id),
    ["a"],
  );
  assert.deepEqual(
    filterByHost(models, "local").map((m) => m.id),
    ["b"],
  );
  assert.equal(filterByHost(models, "all").length, 2);
});

test("sortModels by name is alphabetical", () => {
  const models = [
    hosted("c", "Carol", "1M", "$2"),
    hosted("a", "Alice", "1M", "$9"),
  ];
  assert.deepEqual(
    sortModels(models, "name").map((m) => m.name),
    ["Alice", "Carol"],
  );
});

// Spec for the two functions you implement: largest context first, cheapest price first,
// unparseable / local models pushed to the end of either ranking.
test("sortModels by context ranks the biggest window first", () => {
  const models = [
    hosted("small", "Small", "200K tokens", "$1"),
    hosted("big", "Big", "1M tokens", "$1"),
    local("nolen", "NoLen", "unknown"),
  ];
  assert.deepEqual(
    sortModels(models, "context").map((m) => m.id),
    ["big", "small", "nolen"],
  );
});

test("sortModels by price ranks the cheapest first, local models last", () => {
  const models = [
    local("free", "Free", "128K"),
    hosted("dear", "Dear", "1M", "$10 / $50 per MTok"),
    hosted("cheap", "Cheap", "1M", "$2 / $10 per MTok"),
  ];
  assert.deepEqual(
    sortModels(models, "price").map((m) => m.id),
    ["cheap", "dear", "free"],
  );
});
