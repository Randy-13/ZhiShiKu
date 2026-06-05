export function Stepper({
  steps,
  activeIndex,
  onSelect,
}: {
  steps: string[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
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
  );
}
