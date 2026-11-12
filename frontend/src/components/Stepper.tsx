import { Icon } from "./Icon";
import { closeDetailsOnEscape } from "./detailsKeyboard";

const STEPS = ["Upload", "Audit", "Fix", "Re-audit", "Export"] as const;
export type WorkflowStep = typeof STEPS[number];

export function Stepper({ current }: { current: WorkflowStep }) {
  const active = STEPS.indexOf(current);
  const list = <ol className="workflow-steps" aria-label="Document workflow">
    {STEPS.map((step, index) => <li key={step} aria-current={step === current ? "step" : undefined}>
      <span className="step-marker" aria-hidden="true">{index < active ? <Icon name="success" /> : index + 1}</span>
      <span>{step}{index < active && <span className="visually-hidden"> completed</span>}</span>
    </li>)}
  </ol>;
  return <div className="stepper">
    <div className="stepper-wide">{list}</div>
    <details className="stepper-compact" onKeyDown={closeDetailsOnEscape}>
      <summary>Step {active + 1} of {STEPS.length} · {current}</summary>
      {list}
    </details>
  </div>;
}
