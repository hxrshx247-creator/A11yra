import { useEffect, useRef } from "react";

export function usePageHeading(title: string) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = `${title} | A11yra`;
    heading.current?.focus();
  }, [title]);
  return heading;
}
