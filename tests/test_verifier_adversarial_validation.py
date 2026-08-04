from __future__ import annotations

from copy import deepcopy

import pytest

from hayden_preskill_toy.recovery_adversarial import (
    INVALID_CATEGORY_COUNTS,
    VALID_CATEGORY_COUNTS,
    build_invalid_case,
    build_valid_case,
    campaign_case_count,
    evaluate_case,
    load_default_context,
)
from hayden_preskill_toy.recovery_serialization import artifact_from_dict, artifact_to_dict
from run_verifier_adversarial_validation import run


def test_campaign_definition_has_exact_documented_counts():
    assert campaign_case_count() == (10_000, 1_000)
    assert len({name for name, _, _ in INVALID_CATEGORY_COUNTS}) == len(INVALID_CATEGORY_COUNTS)
    assert len({name for name, _ in VALID_CATEGORY_COUNTS}) == len(VALID_CATEGORY_COUNTS)


def test_every_category_smoke_case_reaches_its_expected_control():
    context = load_default_context()
    for category, _, expected_control in INVALID_CATEGORY_COUNTS:
        result = evaluate_case(context, build_invalid_case(context, category, 0))
        assert not result.observed_valid
        assert result.clean_rejection
        assert result.observed_first_control == expected_control
    for category, _ in VALID_CATEGORY_COUNTS:
        result = evaluate_case(context, build_valid_case(context, category, 0))
        assert result.observed_valid
        assert result.observed_first_control == "none"


def test_signed_logical_action_claim_is_independently_checked():
    context = load_default_context()
    result = evaluate_case(context, build_invalid_case(context, "certificate_claim", 2))
    assert not result.observed_valid
    assert result.observed_first_control == "certificate_signature_claims"


def test_unknown_serialized_fields_are_not_silently_ignored():
    context = load_default_context()
    value = deepcopy(artifact_to_dict(context.artifact))
    value["unknown_adversarial_field"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        artifact_from_dict(value)


def test_smoke_runner_writes_a_valid_report(tmp_path):
    results = tmp_path / "cases.csv"
    summary = tmp_path / "summary.csv"
    report = tmp_path / "report.md"
    assert run(smoke=True, results_path=results, summary_path=summary, report_path=report) == 0
    assert results.exists() and summary.exists() and report.exists()
    assert "**VALIDÉ**" in report.read_text(encoding="utf-8")
