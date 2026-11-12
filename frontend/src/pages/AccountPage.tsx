import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { downloadProductFile, productRequest, selectWorkspace, uploadSample } from "../api/client";
import { Button } from "../components/Button";
import { ProductPage, ProductStatus } from "../components/ProductPage";
import { signOut } from "../components/WorkspaceGate";
import { errorMessage, useWorkspace } from "../hooks/useProduct";
import type { Profile } from "../types/product";

const accountModes = {
  login: "Sign in",
  signup: "Create an account",
  forgot: "Reset your password",
  reset: "Choose a new password",
  verify: "Verify your email",
  invite: "Accept a workspace invitation",
};
export type AccountMode = keyof typeof accountModes;

function nextPath() {
  const fallback = import.meta.env.VITE_SHOW_ADVANCED === "true" ? "/workspace" : "/upload";
  const next = new URLSearchParams(location.search).get("next") ?? fallback;
  try {
    const destination = new URL(next, location.origin);
    if (next.startsWith("/") && destination.origin === location.origin) {
      return destination.pathname + destination.search + destination.hash;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export function AccountPage({ mode }: { mode: AccountMode }) {
  const [linkToken] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token") ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const sample = new URLSearchParams(location.search).get("sample") === "1";
  const sampleFlow = sample && (mode === "signup" || mode === "login");
  const next = sample ? "sample=1" : `next=${encodeURIComponent(nextPath())}`;

  useEffect(() => {
    if (linkToken) history.replaceState(null, "", location.pathname + location.search);
  }, [linkToken]);

  async function openSample(profile: Profile) {
    const personal = profile.workspaces.find((workspace) => workspace.personal);
    if (personal) selectWorkspace(personal.id);
    setSignedIn(true);
    const result = await uploadSample("lecture");
    location.assign(`/audit/${encodeURIComponent(result.document_id)}?sample=lecture`);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const email = fields.get("email");
    const password = fields.get("password");
    setPending(true);
    setError("");
    setMessage("");
    try {
      if (mode === "login" || mode === "invite" && email) {
        const profile = await productRequest<Profile>("/api/auth/login", "POST", { email, password });
        if (mode === "login") {
          if (sampleFlow) await openSample(profile);
          else location.assign(nextPath());
          return;
        }
      }
      if (mode === "invite") {
        const result = await productRequest<{ workspace_id: string }>("/api/invites/accept", "POST", { token: linkToken });
        selectWorkspace(result.workspace_id);
        location.assign("/workspace");
      } else if (mode === "verify" || mode === "reset") {
        await productRequest(`/api/auth/${mode}`, "POST",
          mode === "reset" ? { token: linkToken, password } : { token: linkToken });
        setMessage(mode === "verify" ? "Your email is verified. You can sign in now." : "Your password was changed. Sign in with the new password.");
      } else {
        const result = await productRequest<{ message: string }>(`/api/auth/${mode}`, "POST",
          mode === "forgot" ? { email } : { email, password });
        if (mode === "signup" && sampleFlow) {
          const profile = await productRequest<Profile>("/api/auth/login", "POST", { email, password });
          await openSample(profile);
        } else {
          setMessage(result.message);
        }
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  const needsEmail = ["login", "signup", "forgot", "invite"].includes(mode);
  const needsPassword = ["login", "signup", "reset", "invite"].includes(mode);
  const fromMail = ["reset", "verify", "invite"].includes(mode);
  return <ProductPage title={accountModes[mode]} eyebrow="Educator workspace" className="account-page"
    description={sampleFlow ? "The Stack and Queue lecture will open as soon as you’re signed in." : undefined}>
    {mode === "signup" && import.meta.env.VITE_TEMPORARY_DEMO === "true" &&
      <p>Use a made-up address like judge@example.test and a new password. The temporary demo does not send email.</p>}
    {fromMail && !linkToken ? <p>Open the link from your email to continue.</p> :
      <form className="product-card product-form" onSubmit={submit}>
        {mode === "invite" && <p>Already signed in? Leave the sign-in fields empty to accept with your current account.</p>}
        {needsEmail && <label>Email address{mode !== "invite" && " (required)"}
          <input name="email" type="email" autoComplete="email" required={mode !== "invite"} maxLength={254} />
        </label>}
        {needsPassword && <label>Password{mode !== "invite" && " (required)"}
          <input name="password" type="password" autoComplete={["signup", "reset"].includes(mode) ? "new-password" : "current-password"}
            required={mode !== "invite"} minLength={["signup", "reset"].includes(mode) ? 12 : undefined} maxLength={128}
            aria-describedby={["signup", "reset"].includes(mode) ? "password-help" : undefined} />
        </label>}
        {["signup", "reset"].includes(mode) && <p id="password-help">Use at least 12 characters.</p>}
        <Button type="submit" disabled={pending || signedIn}>{accountModes[mode]}</Button>
        <ProductStatus error={error} message={pending ? signedIn ? "Opening the sample lecture…" : "Working…" : message} />
        {signedIn && error && <a href="/workspace">Continue to your workspace</a>}
      </form>}
    <nav className="product-actions" aria-label="Account options">
      {mode !== "login" && <a href={`/account/login?${next}`}>Sign in</a>}
      {mode === "login" && import.meta.env.VITE_TEMPORARY_DEMO !== "true" && <a href={`/account/forgot?${next}`}>Forgot your password?</a>}
      {mode !== "signup" && <a href={`/account/signup?${next}`}>Create an account</a>}
    </nav>
  </ProductPage>;
}

export function AccountSettings() {
  const { profile } = useWorkspace();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function perform(action: () => Promise<unknown>, success?: string) {
    setPending(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success ?? "");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(false);
    }
  }

  function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void perform(async () => {
      await productRequest("/api/auth/account", "DELETE", { password: form.get("password"), confirm: form.has("confirm") });
      sessionStorage.removeItem("a11yra-workspace");
      location.assign("/");
    });
  }

  return <ProductPage title="Account and data">
    <section className="product-card">
      <h2>{profile.email}</h2>
      <p>{profile.email_verified ? "Email verified" : "Email verification pending"}</p>
      <div className="product-actions">
        {!profile.email_verified && <Button variant="secondary" disabled={pending} onClick={() =>
          perform(() => productRequest("/api/auth/verify/resend", "POST"), "Check your inbox for a verification link.")}>Resend verification email</Button>}
        <Button variant="secondary" disabled={pending} onClick={() =>
          perform(() => downloadProductFile("/api/auth/data", "a11yra-account.json"), "Data export started.")}>Export my data (JSON)</Button>
        <Button variant="quiet" disabled={pending} onClick={() => perform(signOut)}>Sign out</Button>
      </div>
    </section>
    <section className="product-card">
      <h2>Delete my account and data</h2>
      <p>This permanently removes your uploads, reader links, memberships, and personal workspace. Collaborators will lose access to that workspace.</p>
      <form className="product-form" onSubmit={remove}>
        <label>Current password (required)<input name="password" type="password" autoComplete="current-password" required maxLength={128} /></label>
        <label className="product-checkbox"><input name="confirm" type="checkbox" required /> I confirm permanent deletion of my account and data.</label>
        <Button variant="secondary" type="submit" disabled={pending}>Delete my account and all data</Button>
      </form>
    </section>
    <ProductStatus error={error} message={pending ? "Working…" : message} />
  </ProductPage>;
}
