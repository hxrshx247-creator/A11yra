import { useState } from "react";
import type { FormEvent } from "react";
import { deleteDocument, productRequest } from "../api/client";
import { Button, ButtonLink } from "../components/Button";
import { Icon } from "../components/Icon";
import { ProductPage, ProductStatus } from "../components/ProductPage";
import { errorMessage, formatDate, useProduct, useWorkspace } from "../hooks/useProduct";
import type { History, Share, Usage } from "../types/product";
import { Table } from "./WorkspacePage";

export function DocumentHistory({ id }: { id: string }) {
  const { workspace } = useWorkspace();
  const { data, error } = useProduct<History>(`/api/documents/${id}/history`);
  const [deleteError, setDeleteError] = useState("");
  const [pending, setPending] = useState(false);
  const active = data?.status === "active" && new Date(data.expires_at + "Z").getTime() > Date.now();
  const first = data?.versions[0]?.progress;
  const last = data?.versions.at(-1)?.progress;

  async function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      await deleteDocument(id);
      location.assign("/workspace");
    } catch (reason) {
      setDeleteError(errorMessage(reason));
      setPending(false);
    }
  }

  return <ProductPage title="Audit history" description={data?.filename} className="history-page">
    <ProductStatus error={error} message={data ? undefined : "Loading audit history…"} />
    {data && <>
      {active && <div className="product-actions">
        <ButtonLink href={`/audit/${id}`}>Open latest audit <Icon name="arrow" /></ButtonLink>
      </div>}
      {first && last && <section className="product-card">
        <h2>Audit progress</h2>
        <p>{first.passed} of {first.evaluated} → {last.passed} of {last.evaluated} checks passed</p>
        <ol className="product-chart" aria-hidden="true">{data.versions.map((version, index) =>
          <li key={version.audit_id}><span>Audit {index + 1}</span>
            {version.progress.percent !== null && <meter min={0} max={100} value={version.progress.percent} />}
            <span>{version.progress.percent === null ? "No checks evaluated" : `${version.progress.percent}%`}</span>
          </li>)}</ol>
        <Table caption="Audit versions" columns={["Version", "Date", "Checks passed"]}
          rows={data.versions.map((version, index) => [index + 1, formatDate(version.created_at),
            `${version.progress.passed} of ${version.progress.evaluated}`])} />
      </section>}
      {workspace.role !== "viewer" && <>
        <ReaderLinks id={id} publish={Boolean(active)} />
        <details className="product-card">
          <summary>Delete this document</summary>
          <form className="product-form" onSubmit={remove}>
            <p>This removes the file, audit history, and published reader links.</p>
            <label className="product-checkbox"><input type="checkbox" required /> I confirm permanent deletion of this document.</label>
            <Button variant="secondary" type="submit" disabled={pending}>Delete my document now</Button>
            <ProductStatus error={deleteError} />
          </form>
        </details>
      </>}
    </>}
    <a href="/workspace">Back to workspace</a>
  </ProductPage>;
}

export function ReaderLinks({ id, publish }: { id: string; publish: boolean }) {
  const { workspace } = useWorkspace();
  const base = `/api/documents/${id}/shares`;
  const shares = useProduct<Share[]>(base);
  const { data: usage } = useProduct<Usage>(`/api/workspaces/${workspace.id}/usage`);
  const [link, setLink] = useState<(Share & { url: string }) | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function perform(action: () => Promise<void>, success: string) {
    setPending(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    void perform(async () => {
      const result = await productRequest<Share & { url: string }>(base, "POST", {
        days: Number(fields.get("days")), label: fields.get("label") ?? "",
      });
      setLink(result);
      shares.refresh();
    }, "Reader published. Copy its link below.");
  }

  return <section className="product-card">
    <h2>Shareable reader links</h2>
    <p>Anyone with a link can open this version until it expires or you revoke it. Your account email is shown as the contact for reader issues.</p>
    {publish && <form className="product-form" onSubmit={create}>
      <label>Link lifetime<select name="days" defaultValue="7"><option value="1">1 day</option>
        <option value="7">7 days</option><option value="30">30 days, subject to audit retention</option></select></label>
      {usage?.plan.reader_branding && <label>Reader label (optional)<input name="label" maxLength={80} /></label>}
      <Button variant="secondary" type="submit" disabled={pending}>Publish reader link</Button>
    </form>}
    {link && <div className="product-actions product-break">
      <a href={link.url} target="_blank" rel="noreferrer">Open published reader (new tab)</a>
      <Button variant="quiet" disabled={pending}
        onClick={() => perform(() => navigator.clipboard.writeText(link.url), "Reader link copied.")}>Copy link</Button>
    </div>}
    {shares.data?.length === 0 && <p>No active links.</p>}
    {!!shares.data?.length && <ul className="product-list">{shares.data.map((share) => <li className="product-actions" key={share.id}>
      <span>Published {formatDate(share.created_at)}. Expires {formatDate(share.expires_at)}.</span>
      <Button variant="quiet" disabled={pending} onClick={() => perform(async () => {
        await productRequest(`${base}/${share.id}`, "DELETE");
        if (link?.id === share.id) setLink(null);
        shares.refresh();
      }, "Reader link revoked.")}>Revoke link</Button>
    </li>)}</ul>}
    <ProductStatus error={error || shares.error} message={pending ? "Working…" : message} />
  </section>;
}
