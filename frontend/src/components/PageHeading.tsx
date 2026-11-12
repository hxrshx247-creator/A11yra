import type { RefObject } from "react";
import { CubeBackdrop } from "./CubeBackdrop";

export function PageHeading({ headingRef, title, description, eyebrow }: {
  headingRef: RefObject<HTMLHeadingElement | null>;
  title: string;
  description?: string;
  eyebrow?: string;
}) {
  return <div className="page-heading">
    <CubeBackdrop className="page-heading-backdrop" />
    <div className="page-heading-content">
      {eyebrow && <p className="page-eyebrow">{eyebrow}</p>}
      <h1 ref={headingRef} tabIndex={-1}>{title}</h1>
      {description && <p className="product-description">{description}</p>}
    </div>
  </div>;
}
