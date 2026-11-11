from app.audit.score import calculate_progress
from app.models import Check


def test_needs_review_counts_as_evaluated_and_percent_is_rounded():
    checks = [
        Check(id="title", label="Title", result="passed", summary="", finding_ids=[]),
        Check(id="language", label="Language", result="needs_review", summary="", finding_ids=[]),
        Check(id="headings", label="Headings", result="passed", summary="", finding_ids=[]),
        Check(id="links", label="Links", result="not_evaluated", summary="", finding_ids=[]),
    ]

    progress = calculate_progress(checks)

    assert progress.model_dump() == {"passed": 2, "evaluated": 3, "percent": 67}


def test_no_evaluated_checks_has_no_percentage():
    check = Check(id="images", label="Images", result="not_evaluated", summary="", finding_ids=[])
    assert calculate_progress([check]).model_dump() == {"passed": 0, "evaluated": 0, "percent": None}
