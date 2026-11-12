import { useState } from "react";
import type { FormEvent } from "react";
import { downloadProductFile, productRequest, selectWorkspace, uploadSample } from "../api/client";
import { Button, ButtonLink } from "../components/Button";
import { ProductPage, ProductStatus } from "../components/ProductPage";
import { errorMessage, formatDate, useProduct, useWorkspace } from "../hooks/useProduct";
import type { Activity, Dashboard, IntegrationKey, Member, Usage, WorkspaceDocument } from "../types/product";

const sections = { documents: "Documents", dashboard: "Dashboard", activity: "Activity", members: "Members", keys: "API keys" };
export type WorkspaceSection = keyof typeof sections;

function useAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function run(action: () => Promise<unknown>, success = "") {
    if (pending) return;
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
  return { run, pending, error, message: pending ? "Working…" : message };
}

export function WorkspacePage({ section }: { section: WorkspaceSection }) {
  const { profile, workspace } = useWorkspace();
  const base = `/api/workspaces/${workspace.id}`;
  const owner = workspace.role === "owner";
  const editor = workspace.role !== "viewer";
  const allowed = (item: WorkspaceSection) => item === "documents" || (item === "activity" ? editor : owner);
  return <ProductPage title={sections[section]} eyebrow={workspace.name} className="workspace-page">
    <div className="product-toolbar">
      {profile.workspaces.length > 1 && <label>Switch workspace
        <select value={workspace.id} onChange={(event) => {
          selectWorkspace(event.target.value);
          location.assign("/workspace");
        }}>
          {profile.workspaces.map((item) => <option key={item.id} value={item.id}>
            {item.personal ? "Personal workspace" : item.name + " (shared)"}
          </option>)}
        </select>
      </label>}
      <span className="product-role">Role {workspace.role}</span>
      <a href="/account/settings">Account and data</a>
    </div>
    <nav aria-label="Workspace" className="product-tabs">
      {(Object.entries(sections) as [WorkspaceSection, string][]).filter(([item]) => allowed(item)).map(([item, label]) =>
        <a key={item} href={item === "documents" ? "/workspace" : `/workspace/${item}`}
          aria-current={section === item ? "page" : undefined}>{label}</a>)}
    </nav>
    {!allowed(section) ? <ProductStatus error="Your workspace role does not have access to this page." /> :
      section === "documents" ? <Documents base={base} editor={editor} /> :
      section === "activity" ? <ActivityPanel base={base} /> :
      section === "dashboard" ? <DashboardPanel base={base} /> :
      section === "members" ? <Members base={base} verified={profile.email_verified} /> : <Keys base={base} />}
  </ProductPage>;
}

function Documents({ base, editor }: { base: string; editor: boolean }) {
  const docs = useProduct<WorkspaceDocument[]>(`${base}/documents`);
  const { data: usage } = useProduct<Usage>(`${base}/usage`);
  const action = useAction();
  return <>
    <div className="product-actions">
      {editor && <ButtonLink href="/upload">Upload a Word document</ButtonLink>}
      <a href="/checks">What A11yra checks</a>
    </div>
    {usage && <p>You’ve used <strong>{usage.documents_used} of {usage.plan.documents_per_month}</strong> documents this month.
      {" "}<a href="/pricing">See plans</a></p>}
    {docs.data?.length === 0 && editor && <section className="product-card sample-card">
      <h2>Try the workflow with a sample</h2>
      <ol><li>Audit the sample syllabus.</li><li>Fix an issue and run a new audit to verify it.</li><li>Export the learner reader or publish a link.</li></ol>
      <Button disabled={action.pending} onClick={() => action.run(async () => {
        const result = await uploadSample();
        location.assign(`/audit/${result.document_id}`);
      })}>Audit the sample syllabus</Button>
      <ProductStatus {...action} />
    </section>}
    <ProductStatus error={docs.error} message={docs.data ? undefined : "Loading documents…"} />
    {docs.data?.length === 0 && !editor && <p>No documents have been added to this workspace yet.</p>}
    {!!docs.data?.length && <ul className="product-list" aria-label="Workspace documents">{docs.data.map((doc) =>
      <li className="product-card" key={doc.id}>
        <h2>{doc.filename}</h2>
        <p>{doc.status === "active" ? `Files expire ${formatDate(doc.expires_at)}` : "Working files expired. Audit history is available."}</p>
        <div className="product-actions">
          {doc.status === "active" && <a href={`/audit/${doc.id}`} aria-label={`Open audit for ${doc.filename}`}>Open audit</a>}
          <a href={`/history/${doc.id}`} aria-label={`View history for ${doc.filename}`}>View history</a>
        </div>
      </li>)}</ul>}
  </>;
}

function ActivityPanel({ base }: { base: string }) {
  const [query, setQuery] = useState("");
  const source = useProduct<Activity[]>(`${base}/activity`);
  const filtered = useProduct<Activity[]>(query ? `${base}/activity?${query}` : null);
  const { data, error } = query ? filtered : source;
  const actors = Array.from(new Map(source.data?.filter((row) => row.actor_id && row.actor)
    .map((row) => [row.actor_id!, row.actor!])).entries()).sort((first, second) => first[1].localeCompare(second[1]));
  const actions = Array.from(new Set(source.data?.map((row) => row.action))).sort();
  const action = useAction();
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new URLSearchParams();
    new FormData(event.currentTarget).forEach((value, key) => { if (value) values.set(key, String(value)); });
    setQuery(values.toString());
  }
  return <>
    <form className="product-card product-filters" onSubmit={filter} onReset={() => setQuery("")}>
      <label>Actor<select name="actor"><option value="">All actors</option>
        {actors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <label>Action<select name="action"><option value="">All actions</option>
        {actions.map((name) => <option key={name} value={name}>{name.replaceAll("_", " ")}</option>)}</select></label>
      <label>Start date (UTC)<input type="date" name="start" /></label>
      <label>End date (UTC)<input type="date" name="end" /></label>
      <div className="product-actions"><Button type="submit">Apply filters</Button><Button variant="quiet" type="reset">Clear</Button></div>
    </form>
    <Button variant="secondary" disabled={action.pending} onClick={() =>
      action.run(() => downloadProductFile(`${base}/activity?format=csv&${query}`, "a11yra-activity.csv"), "CSV export started.")}>Export activity CSV</Button>
    <ProductStatus error={error || action.error} message={action.message || (data ? undefined : "Loading activity…")} />
    {data && (data.length ? <Table caption="Workspace activity" columns={["Date", "Actor", "Action", "Target"]}
      rows={data.map((row) => [formatDate(row.created_at), row.actor ?? "System or deleted account",
        row.action.replaceAll("_", " "), row.target_type.replaceAll("_", " ")])} /> : <p>No activity matches these filters.</p>)}
  </>;
}

function DashboardPanel({ base }: { base: string }) {
  const { data, error } = useProduct<Dashboard>(`${base}/dashboard`);
  const action = useAction();
  return <>
    <div className="product-actions print-hide">
      <Button variant="secondary" disabled={action.pending} onClick={() =>
        action.run(() => downloadProductFile(`${base}/dashboard?format=csv`, "a11yra-dashboard.csv"), "CSV export started.")}>Export dashboard CSV</Button>
      <Button variant="quiet" onClick={() => window.print()}>Print or save as PDF</Button>
    </div>
    <ProductStatus error={error || action.error} message={action.message || (data ? undefined : "Loading dashboard…")} />
    {data && <>
      <dl className="product-stats">
        {[
          ["Documents audited", data.documents], ["Findings still open", data.open],
          ["Findings verified fixed", data.verified], ["Average audit progress", data.average_percent === null ? "—" : `${data.average_percent}%`],
        ].map(([label, value]) => <div className="product-card" key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      {data.common_issues.length > 0 && <section className="product-card">
        <h2>Most common open issues</h2>
        <ul className="product-chart" aria-hidden="true">{data.common_issues.map(({ check, count }) =>
          <li key={check}><span>{check}</span><meter min={0} max={data.common_issues[0].count} value={count} /><span>{count}</span></li>)}</ul>
        <Table caption="Issue counts" columns={["Check", "Open findings"]}
          rows={data.common_issues.map(({ check, count }) => [check, count])} />
      </section>}
      {data.attention.length > 0 ? <Table caption="Documents by open findings"
        columns={["Document", "Versions", "First audit", "Latest audit", "Open", "Verified"]}
        rows={data.attention.map((doc) => [<a href={`/history/${doc.document_id}`}>{doc.filename}</a>,
          doc.versions, doc.before, doc.after, doc.open, doc.verified])} /> :
        <p>Audit a document to see progress and findings here.</p>}
    </>}
  </>;
}

function Members({ base, verified }: { base: string; verified: boolean }) {
  const list = useProduct<Member[]>(`${base}/members`);
  const action = useAction();
  function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    void action.run(async () => {
      await productRequest(`${base}/invites`, "POST", { email: fields.get("email"), role: fields.get("role") });
      form.reset();
    }, "Invitation queued. The recipient has 7 days to accept.");
  }
  return <>
    <section className="product-card">
      <h2>Invite a colleague</h2>
      {verified ? <form className="product-form" onSubmit={invite}>
        <label>Email address (required)<input name="email" type="email" maxLength={254} required /></label>
        <label>Role<select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option></select></label>
        <p>Viewers can open audits and download exports. Editors can also upload, repair, delete and publish documents.</p>
        <Button type="submit" disabled={action.pending}>Send invitation</Button>
      </form> : <p><a href="/account/settings">Verify your email</a> before sending invitations.</p>}
    </section>
    <ProductStatus error={list.error || action.error} message={action.message || (list.data ? undefined : "Loading members…")} />
    {list.data && <Table caption="Workspace members" columns={["Email", "Role"]}
      rows={list.data.map((item) => [item.email, item.role === "owner" ? "Owner" :
        <select aria-label={`Role for ${item.email}`} value={item.role} disabled={action.pending} onChange={(event) => {
          const role = event.target.value;
          void action.run(async () => {
            await productRequest(`${base}/members/${item.id}`, "PATCH", { role });
            list.refresh();
          }, "Role updated.");
        }}><option value="viewer">Viewer</option><option value="editor">Editor</option></select>])} />}
  </>;
}

function Keys({ base }: { base: string }) {
  const list = useProduct<IntegrationKey[]>(`${base}/keys`);
  const usage = useProduct<Usage>(`${base}/usage`);
  const [secret, setSecret] = useState("");
  const action = useAction();
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = new FormData(form).get("name");
    void action.run(async () => {
      const result = await productRequest<{ key: string }>(`${base}/keys`, "POST", { name });
      setSecret(result.key);
      form.reset();
      list.refresh();
    }, "API key created.");
  }
  return <>
    <p>Audit DOCX files from your own tools with a workspace-scoped API key. <a href="/api/docs">Open API reference</a></p>
    {usage.data?.plan.api_access ? <form className="product-card product-form" onSubmit={create}>
      <label>Key name (required)<input name="name" maxLength={80} required /></label>
      <Button type="submit" disabled={action.pending}>Create API key</Button>
    </form> : <p>API access is available on the <a href="/pricing">Institution plan</a>.</p>}
    {secret && <div className="product-card">
      <p>Copy this key now. It is displayed once.</p>
      <code className="product-break">{secret}</code>
      <div className="product-actions"><Button variant="secondary" onClick={() =>
        action.run(() => navigator.clipboard.writeText(secret), "Key copied.")}>Copy key</Button>
        <Button variant="quiet" onClick={() => setSecret("")}>Hide key</Button></div>
    </div>}
    <ProductStatus error={list.error || action.error} message={action.message || (list.data ? undefined : "Loading API keys…")} />
    {!!list.data?.length && <Table caption="Workspace API keys" columns={["Name", "Last used", "Status"]}
      rows={list.data.map((key) => [key.name, key.last_used_at ? formatDate(key.last_used_at) : "Never",
        key.revoked_at ? "Revoked" : <Button variant="quiet" disabled={action.pending}
          aria-label={`Revoke ${key.name}`} onClick={() => action.run(async () => {
            await productRequest(`${base}/keys/${key.id}`, "DELETE");
            setSecret("");
            list.refresh();
          }, "Key revoked.")}>Revoke</Button>])} />}
  </>;
}

export function Table({ caption, columns, rows }: { caption: string; columns: string[]; rows: React.ReactNode[][] }) {
  return <div className="product-table-wrap" role="region" aria-label={`${caption} table`} tabIndex={0}>
    <table className="product-table">
      <caption>{caption}</caption>
      <thead><tr>{columns.map((column) => <th scope="col" key={column}>{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) =>
        <td key={column}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}
