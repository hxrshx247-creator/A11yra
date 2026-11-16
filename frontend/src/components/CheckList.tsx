import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Audit } from "../types/contract";
import { StatusBadge } from "./StatusBadge";
import { FindingCard } from "./FindingCard";
import { Icon } from "./Icon";

export function CheckList({ audit, canEdit }: { audit: Audit; canEdit: boolean }) {
  const { checks, findings } = audit;
  const [selected, setSelected] = useState(() => {
    const category = new URLSearchParams(window.location.search).get("check");
    const requested = checks.findIndex((check) => check.id === category);
    return requested >= 0 ? requested : checks.findIndex(
      (check) => check.result === "issues" || check.result === "needs_review",
    );
  });
  const activeIndex = Math.max(selected, 0);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    switch (event.key) {
      case "ArrowDown": next = (index + 1) % checks.length; break;
      case "ArrowUp": next = (index - 1 + checks.length) % checks.length; break;
      case "Home": next = 0; break;
      case "End": next = checks.length - 1; break;
      default: return;
    }
    event.preventDefault();
    setSelected(next);
    tabs.current[next]?.focus();
  }

  if (!checks.length) return <p>No checks are available for this audit.</p>;

  return (
    <div className="audit-grid">
      <section className="check-column" aria-labelledby="checks-heading">
        <h2 id="checks-heading">Checks</h2>
        <div className="check-list" role="tablist" aria-labelledby="checks-heading" aria-orientation="vertical">
          {checks.map((check, index) => {
            const activeFindings = findings.filter(
              (finding) => check.finding_ids.includes(finding.id) && finding.status !== "verified_fixed",
            );
            const awaitingVerification = activeFindings.length > 0 &&
              activeFindings.every((finding) => finding.status === "fixed_unverified");
            return (
              <button
                className="check-card"
                id={`check-${check.id}`}
                key={check.id}
                type="button"
                role="tab"
                aria-selected={index === activeIndex}
                aria-controls={`findings-${check.id}`}
                tabIndex={index === activeIndex ? 0 : -1}
                ref={(element) => { tabs.current[index] = element; }}
                onClick={() => setSelected(index)}
                onKeyDown={(event) => handleTabKey(event, index)}
              >
                <span className="check-label">{check.label}</span>
                <StatusBadge status={awaitingVerification ? "fixed_unverified" : check.result} />
              </button>
            );
          })}
        </div>
      </section>
      {checks.map((check, index) => (
        <section
          className="findings-panel"
          key={check.id}
          id={`findings-${check.id}`}
          role="tabpanel"
          aria-labelledby={`check-${check.id}`}
          hidden={index !== activeIndex}
          tabIndex={0}
        >
          {index === activeIndex && (
            <>
              <h2>{check.label} findings</h2>
              <p className="check-summary">{check.summary}</p>
              {check.finding_ids.length ? (
                <ul className="findings-list" role="list">
                  {findings.filter((finding) => check.finding_ids.includes(finding.id)).map(
                    (finding) => (
                      <li key={finding.id}>
                        <FindingCard finding={finding} headingLevel="h3" documentId={canEdit ? audit.document_id : undefined} />
                      </li>
                    ),
                  )}
                </ul>
              ) : check.result === "passed" && <div className="empty-findings">
                <p><Icon name="success" /> No findings for this check.</p>
              </div>}
            </>
          )}
        </section>
      ))}
    </div>
  );
}
