// Offline regression checks for the feed's JSON, date and visit boundaries.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

// Use the existing compiler so the tests need no new dependency or generated files.
const source = readFileSync(new URL("../src/lib/feed.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext },
});
const { formatDay, isNew, loadCatalog, readLastVisit, validateCatalog } =
  await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

const previousVisit = "2026-10-05T12:00:00Z";
const requestStarted = "2026-10-06T12:00:00Z";
const goodItem = {
  id: "one", lab: "anthropic", kind: "news", title: "Launch", summary: "",
  url: "https://www.anthropic.com/news/launch", source: "anthropic-news",
  publishedAt: "2026-09-28T00:00:00Z", firstSeenAt: "2026-10-06T11:00:00Z",
};
const goodCatalog = {
  generatedAt: requestStarted,
  sources: { "anthropic-news": { lastOk: requestStarted, lastError: null } },
  items: [goodItem],
};

function browserState(t) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const storage = new Map([["llm-feed:lastVisit", previousVisit]]);
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value) },
  });
  const RealDate = Date;
  let time = Date.parse(requestStarted);
  globalThis.Date = class extends RealDate {
    constructor(...args) { super(...(args.length ? args : [time])); }
    static now() { return time; }
  };
  t.after(() => {
    globalThis.Date = RealDate;
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
    else delete globalThis.localStorage;
  });
  return { advance: () => { time += 60_000; } };
}

test("date-only publications keep their source day in New York; timestamps stay local", (t) => {
  const previousTZ = process.env.TZ;
  process.env.TZ = "America/New_York";
  t.after(() => {
    if (previousTZ === undefined) delete process.env.TZ;
    else process.env.TZ = previousTZ;
  });
  const stamp = goodItem.publishedAt;
  const utcDay = new Date(stamp).toLocaleDateString(undefined, {
    month: "short", day: "numeric", timeZone: "UTC",
  });
  const localDay = new Date(stamp).toLocaleDateString(undefined, {
    month: "short", day: "numeric", timeZone: "America/New_York",
  });
  assert.notEqual(utcDay, localDay);
  assert.equal(formatDay(stamp, true), utcDay);
  assert.equal(formatDay(stamp), localDay);
});

test("valid catalogs accept unknown fields without stripping them", () => {
  const catalog = structuredClone(goodCatalog);
  catalog.extra = { future: true };
  catalog.items[0].extra = "preserved";
  const before = structuredClone(catalog);
  validateCatalog(catalog);
  assert.deepEqual(catalog, before);
});

const malformed = [null, [], {},
  { ...goodCatalog, items: {} },
  { ...goodCatalog, sources: [] },
  { ...goodCatalog, generatedAt: "yesterday" },
  { ...goodCatalog, sources: { bad: { lastError: {} } } },
  ...Object.entries({ title: {}, summary: [], url: "javascript:alert(1)",
    kind: "other", lab: "other", source: null, firstSeenAt: "yesterday",
    publishedAt: "2026-10-06T12:00:00" }).map(([key, value]) => ({
    ...goodCatalog, items: [{ ...goodItem, [key]: value }],
  })),
  ...["title", "summary", "url", "source", "kind", "publishedAt"].map((key) => ({
    ...goodCatalog, items: [Object.fromEntries(Object.entries(goodItem).filter(
      ([field]) => field !== key,
    ))],
  })),
];
test("malformed catalog containers, display fields, dates and unsafe links are rejected", () => {
  for (const value of malformed) {
    assert.throws(() => validateCatalog(value), /invalid catalog shape/);
  }
});

for (const failure of ["network", "http", "json", "shape"]) {
  test(`${failure} failure leaves the previous visit and new badges intact`, async (t) => {
    browserState(t);
    t.mock.method(globalThis, "fetch", async () => {
      if (failure === "network") throw new Error("offline");
      return { ok: failure !== "http", status: 503, json: async () => {
        if (failure === "json") throw new SyntaxError("bad JSON");
        return {};
      } };
    });
    await assert.rejects(loadCatalog());
    assert.equal(readLastVisit(), previousVisit);
    assert.equal(isNew(goodItem, readLastVisit()), true);
  });
}

test("successful load records request start, keeping later arrivals new", async (t) => {
  const { advance } = browserState(t);
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "./items.json");
    assert.equal(options.cache, "no-store");
    assert.equal(readLastVisit(), previousVisit);
    advance();
    return { ok: true, json: async () => structuredClone(goodCatalog) };
  });
  assert.deepEqual(await loadCatalog(), goodCatalog);
  assert.equal(readLastVisit(), requestStarted);
  assert.equal(isNew({ ...goodItem, firstSeenAt: "2026-10-06T12:00:30Z" }, readLastVisit()), true);
});
