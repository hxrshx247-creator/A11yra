import type { ReactNode } from "react";
import { PageHeading } from "./PageHeading";
import { usePageHeading } from "../hooks/usePageHeading";

export function ProductPage({ title, description, eyebrow, className = "", children }: {
  title: string;
  description?: string;
  eyebrow?: string;
  className?: string;
  children?: ReactNode;
}) {
  const heading = usePageHeading(title);
  return <main id="main" className={`product-page ${className}`} tabIndex={-1}>
    <PageHeading headingRef={heading} title={title} description={description} eyebrow={eyebrow} />
    {children}
  </main>;
}

export function ProductStatus({ error, message }: { error?: string; message?: string }) {
  return error ? <p role="alert" className="form-error">{error}</p> : <p role="status" className="product-status">{message}</p>;
}
