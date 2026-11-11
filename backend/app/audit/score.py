from collections.abc import Sequence

from app.models import AuditProgress, Check


def calculate_progress(checks: Sequence[Check]) -> AuditProgress:
    evaluated = sum(check.result != "not_evaluated" for check in checks)
    passed = sum(check.result == "passed" for check in checks)
    percent = round(100 * passed / evaluated) if evaluated else None
    return AuditProgress(passed=passed, evaluated=evaluated, percent=percent)
