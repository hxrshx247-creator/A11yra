import type { ComponentPropsWithoutRef } from "react";

type Variant = "primary" | "secondary" | "quiet";

export function Button({ variant = "primary", className = "", type = "button", ...props }:
  ComponentPropsWithoutRef<"button"> & { variant?: Variant }) {
  return <button {...props} type={type} className={`button button--${variant} ${className}`} />;
}

export function ButtonLink({ variant = "primary", className = "", ...props }:
  ComponentPropsWithoutRef<"a"> & { variant?: Variant }) {
  return <a {...props} className={`button button--${variant} ${className}`} />;
}
