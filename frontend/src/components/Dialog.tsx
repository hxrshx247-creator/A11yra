import { useId } from "react";
import type { ReactNode, RefObject } from "react";
import { Button } from "./Button";

export function Dialog({ dialogRef, title, closeLabel, children }: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  title: string;
  closeLabel: string;
  children: ReactNode;
}) {
  const titleId = useId();
  return <dialog className="app-dialog" ref={dialogRef} aria-labelledby={titleId}>
    <h2 id={titleId}>{title}</h2>
    {children}
    <Button variant="secondary" autoFocus onClick={() => dialogRef.current?.close()}>{closeLabel}</Button>
  </dialog>;
}
