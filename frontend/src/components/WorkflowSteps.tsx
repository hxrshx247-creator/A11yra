const STEPS = ["Upload", "Audit", "Fix", "Re-audit", "Export"] as const;

export function WorkflowSteps({ current }: { current: typeof STEPS[number] }) {
  return (
    <ol className="workflow-steps" aria-label="Document workflow">
      {STEPS.map((step) => <li key={step} aria-current={step === current ? "step" : undefined}>{step}</li>)}
    </ol>
  );
}
