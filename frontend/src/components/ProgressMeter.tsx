import type { Audit } from "../types/contract";

export function ProgressMeter({ progress }: { progress: Audit["progress"] }) {
  const { passed, evaluated, percent } = progress;
  const count = `${passed} of ${evaluated} checks passed`;
  return (
    <section className="audit-progress" aria-labelledby="audit-progress-heading">
      <div>
        <h2 id="audit-progress-heading">Audit progress</h2>
        <p>{percent === null ? "No checks were evaluated." : count}</p>
      </div>
      {percent !== null && (
        <>
          <span className="audit-percent" aria-hidden="true">{percent}%</span>
          <progress max={100} value={percent} aria-labelledby="audit-progress-heading" aria-valuetext={count} />
        </>
      )}
    </section>
  );
}
