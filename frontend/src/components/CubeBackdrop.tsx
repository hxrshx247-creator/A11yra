import { useId } from "react";

export function CubeBackdrop({ className }: { className: string }) {
  const id = useId();
  const pattern = id + "-pattern";
  const shape = id + "-shape";

  return <svg className={className} aria-hidden="true" focusable="false">
    <defs>
      <pattern id={pattern} width="52" height="90" patternUnits="userSpaceOnUse"
        fill="none" stroke="var(--cube)" strokeWidth="1.2">
        <path id={shape} d="M26 0L52 15V45L26 60L0 45V15ZM0 15L26 30L52 15M26 30V60" />
        <use href={"#" + shape} x="26" y="45" />
        <use href={"#" + shape} x="-26" y="45" />
        <use href={"#" + shape} x="26" y="-45" />
        <use href={"#" + shape} x="-26" y="-45" />
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill={"url(#" + pattern + ")"} />
  </svg>;
}
