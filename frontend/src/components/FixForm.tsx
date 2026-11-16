import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { submitFix } from "../api/client";
import type { CheckId, Finding, Fix, FixType } from "../types/contract";
import { Button } from "./Button";
import { Icon } from "./Icon";

export const FIX_TYPES: Partial<Record<CheckId, FixType>> = {
  headings: "set_heading",
  title: "set_title",
  language: "set_language",
  images: "set_alt_text",
  tables: "set_table_header",
  links: "set_link_text",
};

const TEXT_FIELDS = {
  set_title: { name: "title", label: "Document title", help: "Use a short title that identifies the document." },
  set_language: { name: "lang", label: "Language tag", help: "For example, en-IN for English (India) or hi for Hindi." },
  set_link_text: { name: "new_text", label: "New link label", help: "Describe the destination or action. The link will keep its current destination." },
} as const;

export function FixForm({ documentId, finding, type, onApplied }: {
  documentId: string;
  finding: Finding;
  type: FixType;
  onApplied: () => void;
}) {
  const [decorative, setDecorative] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const errorSummary = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorSummary.current?.focus(); }, [error, pending]);

  const field = type === "set_title" || type === "set_language" || type === "set_link_text"
    ? TEXT_FIELDS[type]
    : undefined;
  const describedBy = error ? "repair-help repair-error" : "repair-help";

  async function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const data = new FormData(event.currentTarget);
    let payload: Fix["payload"] = {};
    if (field) payload = { [field.name]: String(data.get(field.name) ?? "").trim() };
    if (type === "set_alt_text") payload = decorative
      ? { decorative: true }
      : { alt_text: String(data.get("alt_text") ?? "").trim() };
    if (type === "set_heading") payload = { heading_level: Number(data.get("heading_level")) };

    setError("");
    setPending(true);
    try {
      const result = await submitFix(documentId, { finding_id: finding.id, type, payload });
      if (result.applied.some((fix) => fix.finding_id === finding.id)) onApplied();
      else setError(result.skipped[0]?.reason ?? "The fix could not be applied.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The fix could not be applied.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="repair-form" onSubmit={apply} aria-labelledby="repair-heading">
      <h2 id="repair-heading">Approve a fix</h2>
      {error && <p className="form-error" id="repair-error" ref={errorSummary} tabIndex={-1}><Icon name="error" />{error}</p>}
      {field && (
        <>
          <label htmlFor="repair-input">{field.label} (required)</label>
          <p id="repair-help">{field.help}</p>
          <input id="repair-input" name={field.name} type="text" required
            defaultValue={finding.suggested_value}
            maxLength={type === "set_title" ? 255 : undefined}
            aria-describedby={describedBy} aria-invalid={error ? true : undefined} />
        </>
      )}
      {type === "set_alt_text" && (
        <>
          <fieldset aria-describedby={describedBy}>
            <legend>What does this picture do? (required)</legend>
            <label className="choice"><input type="radio" name="picture-purpose" checked={!decorative} onChange={() => setDecorative(false)} /> Conveys information</label>
            <label className="choice"><input type="radio" name="picture-purpose" checked={decorative} onChange={() => setDecorative(true)} /> Decorative</label>
          </fieldset>
          <p id="repair-help">Inspect the picture in the flagged preview. Choose Decorative when the picture adds no information.</p>
          <div className="repair-textarea" hidden={decorative}>
            <label htmlFor="repair-alt">Alt text (required)</label>
            <textarea id="repair-alt" name="alt_text" rows={4} required={!decorative} defaultValue={finding.preview ?? ""}
              disabled={decorative} aria-describedby={describedBy} aria-invalid={error ? true : undefined} />
          </div>
        </>
      )}
      {type === "set_heading" && <>
        <p id="repair-help">Preview in context: “{finding.preview ?? finding.evidence}” Choose the correct outline level before applying.</p>
        <label htmlFor="heading-level">Convert to heading level</label>
        <select id="heading-level" name="heading_level" defaultValue={finding.suggested_value ?? /Heading ([1-6])/.exec(finding.suggestion)?.[1] ?? "2"}>
          {[1, 2, 3, 4, 5, 6].map((level) => <option key={level} value={level}>Heading {level}</option>)}
        </select>
      </>}
      {type === "set_table_header" && (
        <>
          <p id="repair-help">Check the flagged table to confirm that its first row names the columns.</p>
          <label className="choice"><input type="checkbox" required aria-describedby={describedBy} /> Mark the first row as the header (required)</label>
        </>
      )}
      <Button type="submit" aria-disabled={pending}>Apply fix</Button>
      <span role="status">{pending ? "Applying fix…" : ""}</span>
    </form>
  );
}
