// ABOUTME: The model catalog page: one card per model with its role, specs, strengths and weaknesses.
// ABOUTME: Data is the bundled models.json; display rules live in lib/models.ts. No network at all.
import { useMemo, useState } from "react";
import { Chips } from "./Chips";
import {
  MODEL_CATALOG,
  PROVIDERS,
  PROVIDER_NAMES,
  filterModels,
  formatReviewedAt,
  orderModels,
  specsOf,
  type Provider,
} from "./lib/models";

function Points(props: { heading: string; kind: string; points: string[] }) {
  return (
    <div className={`points ${props.kind}`}>
      <h3>{props.heading}</h3>
      <ul>
        {props.points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </div>
  );
}

export default function Models() {
  const [provider, setProvider] = useState<Provider | "all">("all");
  const shown = useMemo(
    () => orderModels(filterModels(MODEL_CATALOG.models, provider)),
    [provider],
  );

  return (
    <>
      <p className="muted subtitle">
        What to reach for, and what each model is bad at · hand-reviewed{" "}
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
      </div>

      <ol className="feed">
        {shown.map((model) => (
          <li key={model.id} className={`card lab-${model.provider}`}>
            <div className="meta">
              <span className="tag">{PROVIDER_NAMES[model.provider]}</span>
              {specsOf(model).map((spec) => (
                <span key={spec} className="muted">
                  {spec}
                </span>
              ))}
            </div>
            <h2>
              <a href={model.docs} target="_blank" rel="noopener noreferrer">
                {model.name}
              </a>
            </h2>
            <p className="summary">{model.role}</p>
            <div className="assessment">
              <Points
                heading="Strengths"
                kind="good"
                points={model.strengths}
              />
              <Points
                heading="Weaknesses"
                kind="bad"
                points={model.weaknesses}
              />
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}
