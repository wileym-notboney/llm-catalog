// ABOUTME: The model catalog page: a pick-to-compare board that lines models up side by side.
// ABOUTME: Data is the bundled models.json; filter/sort rules live in lib/models.ts. No network at all.
import { type ReactNode, useMemo, useState } from "react";
import { Chips } from "./Chips";
import {
  type Host,
  MODEL_CATALOG,
  type Model,
  PROVIDERS,
  PROVIDER_NAMES,
  type Provider,
  type Sort,
  SORTS,
  SORT_NAMES,
  filterByHost,
  filterModels,
  formatReviewedAt,
  orderModels,
  sortModels,
} from "./lib/models";

const HOSTS: Exclude<Host, "all">[] = ["hosted", "local"];
const HOST_NAMES: Record<string, string> = { hosted: "Hosted", local: "Local" };

// The attribute rows of the board, top to bottom. Specs come first so they align for scanning;
// strengths/weaknesses are the two rich rows that expand/collapse together.
const SPEC_ROWS: { label: string; cell: (model: Model) => string }[] = [
  { label: "Role", cell: (model) => model.role },
  { label: "Context", cell: (model) => model.context },
  { label: "Price / size", cell: (model) => model.price ?? model.size ?? "—" },
];

// Start the board with the three models the editor's order puts first, so it is never empty.
const DEFAULT_SELECTION = orderModels(MODEL_CATALOG.models)
  .slice(0, 3)
  .map((model) => model.id);

function Points(props: { points: string[] }) {
  return (
    <ul className="board-points">
      {props.points.map((point) => (
        <li key={point}>{point}</li>
      ))}
    </ul>
  );
}

export default function Models() {
  const [provider, setProvider] = useState<Provider | "all">("all");
  const [host, setHost] = useState<Host>("all");
  const [sort, setSort] = useState<Sort>("catalog");
  const [expanded, setExpanded] = useState(true);
  const [selected, setSelected] = useState<string[]>(DEFAULT_SELECTION);

  // The pool offered in the picker, after the two filters and the chosen sort.
  const pool = useMemo(
    () =>
      sortModels(
        filterByHost(filterModels(MODEL_CATALOG.models, provider), host),
        sort,
      ),
    [provider, host, sort],
  );

  // The board columns: the picked models, in the same order as the pool.
  const board = useMemo(
    () => pool.filter((model) => selected.includes(model.id)),
    [pool, selected],
  );

  const toggle = (id: string) =>
    setSelected((ids) =>
      ids.includes(id) ? ids.filter((other) => other !== id) : [...ids, id],
    );

  return (
    <>
      <p className="muted subtitle">
        Pick models to line them up side by side · hand-reviewed{" "}
        {formatReviewedAt(MODEL_CATALOG.reviewedAt)}
      </p>

      <div className="filters">
        <Chips
          label="Provider"
          options={PROVIDERS}
          value={provider}
          names={PROVIDER_NAMES}
          onChange={setProvider}
        />
        <Chips
          label="Hosting"
          options={HOSTS}
          value={host}
          names={HOST_NAMES}
          onChange={setHost}
        />
        <div className="chips" role="group" aria-label="Sort">
          {SORTS.map((option) => (
            <button
              key={option}
              type="button"
              className="chip"
              aria-pressed={sort === option}
              onClick={() => setSort(option)}
            >
              {SORT_NAMES[option]}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="chip"
          aria-pressed={expanded}
          onClick={() => setExpanded((on) => !on)}
        >
          {expanded ? "Collapse detail" : "Expand detail"}
        </button>
      </div>

      <div className="picker" role="group" aria-label="Models to compare">
        {pool.map((model) => (
          <button
            key={model.id}
            type="button"
            className={`chip lab-${model.provider}`}
            aria-pressed={selected.includes(model.id)}
            onClick={() => toggle(model.id)}
          >
            {model.name}
          </button>
        ))}
      </div>

      {board.length === 0 ? (
        <p className="banner">Pick one or more models above to compare them.</p>
      ) : (
        <div className="board-scroll">
          <div
            className="board"
            style={{
              gridTemplateColumns: `max-content repeat(${board.length}, minmax(200px, 1fr))`,
            }}
          >
            <div className="board-corner" />
            {board.map((model) => (
              <div
                key={model.id}
                className={`board-head lab-${model.provider}`}
              >
                <span className="tag">{PROVIDER_NAMES[model.provider]}</span>
                <a href={model.docs} target="_blank" rel="noopener noreferrer">
                  {model.name}
                </a>
              </div>
            ))}

            {SPEC_ROWS.map((row) => (
              <Row key={row.label} label={row.label}>
                {board.map((model) => (
                  <div key={model.id} className="board-cell">
                    {row.cell(model)}
                  </div>
                ))}
              </Row>
            ))}

            {expanded && (
              <>
                <Row label="Strengths" kind="good">
                  {board.map((model) => (
                    <div key={model.id} className="board-cell">
                      <Points points={model.strengths} />
                    </div>
                  ))}
                </Row>
                <Row label="Weaknesses" kind="bad">
                  {board.map((model) => (
                    <div key={model.id} className="board-cell">
                      <Points points={model.weaknesses} />
                    </div>
                  ))}
                </Row>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Row(props: { label: string; kind?: string; children: ReactNode }) {
  return (
    <>
      <div className={`board-label ${props.kind ?? ""}`}>{props.label}</div>
      {props.children}
    </>
  );
}
