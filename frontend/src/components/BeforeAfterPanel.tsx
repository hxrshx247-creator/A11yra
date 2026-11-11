import type { Audit, ReauditResponse } from "../types/contract";

function ProgressSummary({ title, progress }: { title: string; progress: Audit["progress"] }) {
  return (
    <div className="compare-card">
      <h3>{title}</h3>
      {progress.percent === null ? <p>No checks were evaluated.</p> : (
        <>
          <p className="audit-percent">{progress.percent}%</p>
          <p>{progress.passed} of {progress.evaluated} checks passed</p>
        </>
      )}
    </div>
  );
}

export function BeforeAfterPanel({ result }: { result: ReauditResponse }) {
  const { audit, diff } = result;
  const groups = [
    { label: "Verified fixed", ids: diff.verified_fixed },
    { label: "Still open", ids: diff.still_open },
    { label: "Needs review", ids: diff.needs_review },
    { label: "New findings", ids: diff.new_findings },
  ];
  const findings = new Map(audit.findings.map((finding) => [finding.id, finding]));
  const labels = new Map(audit.checks.map((check) => [check.id, check.label]));

  return (
    <>
      <section aria-labelledby="compare-progress">
        <h2 id="compare-progress">Audit progress</h2>
        <div className="compare-grid">
          <ProgressSummary title="Before re-audit" progress={diff.progress_before} />
          <ProgressSummary title="After re-audit" progress={diff.progress_after} />
        </div>
      </section>
      <section aria-labelledby="compare-changes">
        <h2 id="compare-changes">Changes in findings</h2>
        <div className="compare-grid">
          {groups.map(({ label, ids }) => (
            <section key={label} className="compare-card">
              <h3>{label} ({ids.length})</h3>
              {ids.length === 0 ? <p>None</p> : (
                <ul>
                  {ids.map((id) => {
                    const finding = findings.get(id);
                    return finding && <li key={id}>
                      <a href={`/audit/${audit.document_id}?check=${finding.check_id}`}>
                        {labels.get(finding.check_id)} · {finding.location}
                      </a>
                    </li>;
                  })}
                </ul>
              )}
            </section>
          ))}
        </div>
      </section>
    </>
  );
}
