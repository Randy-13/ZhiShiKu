import type { CSSProperties } from "react";

export function Stepper({
  steps,
  activeIndex,
  progressIndex,
  maxSelectableIndex,
  activeLabel,
  onSelect,
}: {
  steps: string[];
  activeIndex: number;
  progressIndex?: number;
  maxSelectableIndex?: number;
  activeLabel?: string;
  onSelect: (index: number) => void;
}) {
  const clampedIndex = Math.max(0, Math.min(activeIndex, steps.length - 1));
  const clampedProgressIndex = Math.max(0, Math.min(progressIndex ?? activeIndex, steps.length - 1));
  const clampedMaxSelectableIndex = Math.max(0, Math.min(maxSelectableIndex ?? clampedProgressIndex, steps.length - 1));
  const progress = steps.length <= 1 ? 0 : (clampedProgressIndex / (steps.length - 1)) * 100;
  const stepperStyle = {
    "--step-progress": `${progress}%`,
    "--step-progress-ratio": `${progress / 100}`,
  } as CSSProperties;

  return (
    <div className="stepper-panel">
      <div className="stepper-meta">
        <strong>{activeLabel ?? steps[activeIndex] ?? steps[0]}</strong>
        <span>
          {Math.min(activeIndex + 1, steps.length)} / {steps.length}
        </span>
      </div>
      <div className="stepper" style={stepperStyle}>
        {steps.map((step, index) => {
          const disabled = index > clampedMaxSelectableIndex;
          const classes = [
            "step",
            index === clampedIndex ? "active" : "",
            index < clampedProgressIndex ? "done" : "",
            index === clampedProgressIndex ? "current" : "",
            disabled ? "disabled" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              className={classes}
              type="button"
              key={step}
              disabled={disabled}
              aria-current={index === clampedIndex ? "step" : undefined}
              onClick={() => onSelect(index)}
            >
              <span>{index + 1}</span>
              <strong>{step}</strong>
            </button>
          );
        })}
      </div>
    </div>
  );
}
