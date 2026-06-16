export function Stepper({
  steps,
  activeIndex,
  activeLabel,
  onSelect,
}: {
  steps: string[];
  activeIndex: number;
  activeLabel?: string;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="stepper-panel">
      <div className="stepper-meta">
        <strong>{activeLabel ?? steps[activeIndex] ?? steps[0]}</strong>
        <span>
          {Math.min(activeIndex + 1, steps.length)} / {steps.length}
        </span>
      </div>
      <div className="stepper">
        {steps.map((step, index) => (
          <button
            className={index === activeIndex ? "step active" : index < activeIndex ? "step done" : "step"}
            type="button"
            key={step}
            onClick={() => onSelect(index)}
          >
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </button>
        ))}
      </div>
    </div>
  );
}
