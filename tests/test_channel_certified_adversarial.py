from pathlib import Path

from run_channel_certified_adversarial_validation import run


def test_channel_certified_adversarial_smoke(tmp_path: Path):
    results = tmp_path / "results.csv"
    summary = tmp_path / "summary.csv"
    report = tmp_path / "report.md"
    assert run(
        cases_per_category=1,
        results=results,
        summary=summary,
        report=report,
    ) == 0
    assert results.exists() and summary.exists() and report.exists()
    assert "VALIDÉ" in report.read_text(encoding="utf-8")
