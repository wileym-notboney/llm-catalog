// ABOUTME: The filter chip row shared by the feed and the model catalog.
// ABOUTME: "all" is always the first option and is what every filter starts on.

export function Chips<T extends string>(props: {
  label: string;
  options: readonly T[];
  value: T | "all";
  names?: Record<string, string>;
  onChange: (value: T | "all") => void;
}) {
  return (
    <div className="chips" role="group" aria-label={props.label}>
      {(["all", ...props.options] as const).map((option) => (
        <button
          key={option}
          type="button"
          className="chip"
          aria-pressed={props.value === option}
          onClick={() => props.onChange(option)}
        >
          {option === "all" ? "All" : (props.names?.[option] ?? option)}
        </button>
      ))}
    </div>
  );
}
