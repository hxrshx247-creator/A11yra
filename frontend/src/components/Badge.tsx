import type { ReactNode } from "react";

export function Badge({ tone, children }: {
  tone: "success" | "warning" | "danger" | "neutral";
  children: ReactNode;
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
