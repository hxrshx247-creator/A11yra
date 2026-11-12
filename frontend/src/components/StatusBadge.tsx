import { Icon } from "./Icon";

const STATUSES = {
  passed: ["Passed", "success"],
  verified_fixed: ["Verified fixed", "success"],
  issues: ["Needs attention", "error"],
  high: ["High severity", "error"],
  needs_review: ["Needs review", "review"],
  medium: ["Medium severity", "warning"],
  low: ["Low severity", "open"],
  open: ["Open", "open"],
  not_evaluated: ["Not checked", "unchecked"],
  fixed_unverified: ["Fixed, awaiting verification", "waiting"],
  new: ["New findings", "info"],
  still_open: ["Still open", "open"],
} as const;

export function StatusBadge({ status, count }: { status: keyof typeof STATUSES; count?: number }) {
  const [label, treatment] = STATUSES[status];
  return <span className={`badge badge--${treatment}`}>
    <Icon name={treatment} />
    <span>{label}{count === undefined ? "" : ` (${count})`}</span>
  </span>;
}
