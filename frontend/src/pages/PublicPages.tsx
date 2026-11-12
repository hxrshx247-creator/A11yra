import { useEffect, useState } from "react";
import planPrices from "../../../backend/app/product/plan_prices.json";
import { Button, ButtonLink } from "../components/Button";
import { ProductPage, ProductStatus } from "../components/ProductPage";
import { useProduct } from "../hooks/useProduct";
import type { Plans } from "../types/product";

declare const __SUPPORT_EMAIL__: string;
const supportEmail = __SUPPORT_EMAIL__;
const supportLink = supportEmail ? `mailto:${encodeURIComponent(supportEmail).replace("%40", "@")}` : null;
const lastUpdated = "2026-11-12";

export const publicRoutes = {
  "/checks": "What A11yra checks",
  "/security": "Security & privacy",
  "/accessibility": "Accessibility statement",
  "/terms": "Terms",
  "/privacy": "Privacy policy",
  "/support": "Contact & support",
  "/changelog": "Changelog",
  "/status": "Service status",
} as const;
export type PublicRoute = keyof typeof publicRoutes;

const planNames = ["free", "educator", "institution"] as const;
const included = (value: boolean) => value ? "Included" : "Not included";

export function Pricing() {
  const { data, error } = useProduct<Plans>("/api/plans");
  const rows = data ? [
    ["Price", "", ...planNames.map((name) => name === "free" ? "Free during the pilot" :
      planPrices[name] === null ? "Pricing set after the pilot" : "Contact us for pricing")],
    ["Documents per month", "Monthly limits make room for workspaces of different sizes.",
      ...planNames.map((name) => data.plans[name].documents_per_month)],
    ["Maximum upload size", "5 MB keeps trial uploads quick.",
      ...planNames.map((name) => `${data.plans[name].max_file_bytes / 1_000_000} MB`)],
    ["Workspace seats", "More seats let larger teams share the review work.",
      ...planNames.map((name) => data.plans[name].seats)],
    ["Audit history", "History limits help keep audit records only as long as needed.",
      ...planNames.map((name) => `Up to ${data.plans[name].history_days} days`)],
    ["API access", "The Institution plan supports automated reviews.",
      ...planNames.map((name) => included(data.plans[name].api_access))],
    ["Reader branding", "Institutions can give readers a consistent identity.",
      ...planNames.map((name) => included(data.plans[name].reader_branding))],
  ] : [];

  return <ProductPage title="Pricing"
    description="Free is for trying A11yra, Educator is for regular course work, and Institution is for departments and schools.">
    <ProductStatus error={error} message={data ? undefined : "Loading plans…"} />
    {data && <>
      <p className="product-notice">{data.billing_demo ? "Billing in demo mode. No payment is collected." :
        "Stripe test checkout is enabled. Use test cards only."}</p>
      <p><strong>No one is charged during the pilot.</strong></p>
      <p className="pricing-scroll-hint">Scroll the table to see all three plans.</p>
      <div className="product-table-wrap pricing-table-wrap" role="region" aria-label="Plan comparison" tabIndex={0}>
        <table className="product-table pricing-table">
          <caption>Compare plans</caption>
          <thead><tr>
            <th scope="col">Feature</th>
            {planNames.map((name) => <th scope="col" key={name}>{data.plans[name].name}</th>)}
          </tr></thead>
          <tbody>{rows.map(([label, reason, ...values]) => <tr key={label}>
            <th scope="row">{label}{reason && <span className="pricing-reason">{reason}</span>}</th>
            {values.map((value, index) => <td key={planNames[index]}>{value}</td>)}
          </tr>)}</tbody>
        </table>
      </div>
      <div className="product-actions pricing-actions">
        <ButtonLink href="/account/signup">Join the pilot</ButtonLink>
        {supportLink ? <ButtonLink href={supportLink} variant="secondary">Request a pilot</ButtonLink>
          : <Button variant="secondary" disabled>Request a pilot</Button>}
      </div>
      {!supportLink && <p>Institution pilot requests are unavailable right now.</p>}
      <p>Educator is planned per seat and Institution as a department or site licence. Final pricing will be set after the pilot.</p>
    </>}
  </ProductPage>;
}

function ReviewDate({ label }: { label: string }) {
  return <p>{label}: <time dateTime={lastUpdated}>12 November 2026</time></p>;
}

function Readiness() {
  const { data, error } = useProduct<{ status: string }>("/api/ready");
  const [checked, setChecked] = useState<Date>();
  useEffect(() => {
    if (data || error) setChecked(new Date());
  }, [data, error]);
  return <p role="status">Readiness check: {checked ? data?.status === "ready" ? "passed" : "failed" : "checking…"}
    {checked && <> · <time dateTime={checked.toISOString()}>{checked.toLocaleString()}</time></>}</p>;
}

export function PublicPage({ route }: { route: PublicRoute }) {
  return <ProductPage title={publicRoutes[route]} className="public-copy">
    {route === "/checks" && <>
      <p>A11yra checks six common barriers in born-digital Word documents.</p>
      <ul><li>Document title</li><li>Default language</li><li>Heading structure</li><li>Image descriptions</li>
        <li>Table headers</li><li>Link text</li></ul>
      <h2>Review with a person</h2>
      <p>Review the quality of descriptions, reading order in complex layouts, meaning, and suitability for learners. Check the exported document and reader with assistive technology.</p>
      <p>Heading issues are recommendations. Change heading styles in Word and upload the updated copy. Use re-audit to verify repairs applied in A11yra.</p>
      <div className="product-actions"><ButtonLink href="/upload">Check a Word document</ButtonLink></div>
    </>}
    {route === "/security" && <>
      <ul>
        <li>Workspace roles control access to documents, audit history and activity.</li>
        <li>Argon2id protects passwords. Protected cookies keep account sessions signed in.</li>
        <li>Private storage holds the original and working Word files and the current audit. The database holds metadata, audit summaries and short finding-evidence snippets that may include document text.</li>
        <li>Working files expire after 24 hours by default, even after a download. Audit history and activity have separate retention periods.</li>
        <li>Anyone with a published reader link can view its contents until it expires or is revoked.</li>
      </ul>
      <p><a href="/privacy">Read the full privacy policy</a></p>
    </>}
    {route === "/accessibility" && <>
      <ReviewDate label="Last reviewed" />
      <section>
        <h2>What we test</h2>
        <ul>
          <li>Keyboard navigation and visible focus.</li>
          <li>Contrast and layout at narrow widths.</li>
          <li>Automated accessibility checks on the teacher app and exported reader.</li>
        </ul>
      </section>
      <section>
        <h2>Known gaps</h2>
        <ul>
          <li>Read-along varies by browser.</li>
          <li>Complex Word layouts can lose structure during conversion.</li>
          <li>A person needs to review the quality of image descriptions.</li>
          <li>Manual testing with assistive-technology users is still needed.</li>
        </ul>
      </section>
      <p><a href="/support">Report an accessibility problem</a> and include the page, your browser and assistive technology, and the step that caused trouble.</p>
    </>}
    {route === "/terms" && <>
      <p><strong>Pilot version</strong></p>
      <ReviewDate label="Last updated" />
      <section>
        <h2>Using and sharing documents</h2>
        <p>Use A11yra to review and repair Word documents you have permission to upload. You are responsible for the contents you publish and for choosing who receives learner links.</p>
      </section>
      <section>
        <h2>Review your exports</h2>
        <p>Review exports for accuracy and accessibility before distributing them. Automated checks cover six common barriers and cannot guarantee legal or accessibility outcomes.</p>
      </section>
      <section>
        <h2>Pilot availability</h2>
        <p>The pilot has usage limits and may change or become unavailable. Save copies you need before they expire.</p>
      </section>
      <p><a href="/support">Contact the A11yra team</a> for questions about these terms.</p>
    </>}
    {route === "/privacy" && <>
      <p><strong>Pilot version</strong></p>
      <ReviewDate label="Last updated" />
      <section>
        <h2>What we store</h2>
        <p>We store your email, password hash, workspace membership, document filename and size, audit findings, and operational activity. Short finding-evidence snippets in the database can include text from the document.</p>
      </section>
      <section>
        <h2>How long</h2>
        <p>The original and working Word files and current audit stay in private storage until expiry or explicit deletion, even after download. The default file lifetime is 24 hours.</p>
        <p>Audit history is normally kept for up to 7 days on Free and 30 days on Educator and Institution. Activity is kept for 30 days by default. Deployment settings can change these periods.</p>
      </section>
      <section>
        <h2>Who can see it</h2>
        <p>Workspace roles control access to documents and activity. Anyone holding a published link can view the stored reader and its report contact until expiry or revocation. Links last up to 30 days and cannot outlast audit history.</p>
      </section>
      <section>
        <h2>Cookies and logs</h2>
        <p>Account and security cookies keep you signed in. The reader saves preferences in your browser. Service logs can record a reader request’s route and status without recording its link token or a learner identity. A11yra does not handle card details.</p>
      </section>
      <section>
        <h2>Your controls</h2>
        <p>Delete a document from its audit history page to remove its files, audit history, repair and export records, and published readers. Activity and quota records can remain until their own expiry.</p>
        <p>In <a href="/account/settings">Account and data</a> you can export your data or delete your account. Deletion removes your profile, sessions, account links, memberships, invitations, uploads, published readers and personal workspace, including its API keys.</p>
        <p>Other workspaces keep their own data. Their repair and export records lose your account reference. Activity events can remain until expiry with identifying fields removed from entries tied to your account.</p>
      </section>
      <section>
        <h2>Backups and copies</h2>
        <p>A11yra creates no automatic backups. The A11yra team sets expiry for any backups or service logs it keeps. Copies already downloaded or delivered by email are controlled by their recipients or providers.</p>
      </section>
    </>}
    {route === "/support" && <>
      {supportLink ? <p>Email <a href={supportLink}>{supportEmail}</a>.</p> :
        <p>Contact the person who shared your reader or your workspace owner.</p>}
      {import.meta.env.DEV && !supportLink && <p className="product-notice">Development only. Set SUPPORT_EMAIL to show a support email link.</p>}
      <h2>What to include in a report</h2>
      <ol>
        <li>The page and what you were trying to do.</li>
        <li>The step that caused trouble and what happened.</li>
        <li>Your browser and any assistive technology you use.</li>
      </ol>
      <p>Leave out passwords, access links and confidential document contents.</p>
    </>}
    {route === "/changelog" && <ul>
      <li><strong>0.1 Audit and repair</strong> · <time dateTime="2026-11-11">11 November 2026</time></li>
      <li><strong>0.2 Learner reader and offline export</strong> · <time dateTime="2026-11-11">11 November 2026</time></li>
      <li><strong>0.3 Accounts, workspaces and published links</strong> · <time dateTime="2026-11-12">12 November 2026</time></li>
    </ul>}
    {route === "/status" && <Readiness />}
  </ProductPage>;
}
