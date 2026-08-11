"""Mini-spec V23 (docs/PLAN.md, Phase F) — cổng chất lượng tự động.

``evaluate()`` chỉ ĐỌC shape thật của ``quality_report.json`` (xem
``DubPipeline._build_quality_report`` trong autodub/pipeline.py) — fixture
dựng tay dưới đây khớp đúng field ``summary`` mà hàm đó sinh ra, không cần
chạy pipeline thật.
"""
from __future__ import annotations

from autodub.quality_gate import QualityThresholds, evaluate


def _report(**summary_overrides) -> dict:
    summary = {
        "segments_total": 100,
        "segments_ok": 100,
        "segments_shifted": 0,
        "max_shift_s": 0.0,
        "segments_compressed": 0,
        "segments_overlapped": 0,
        "total_overlap_s": 0.0,
        "segments_over_budget": 0,
        "segments_speed_fallback": 0,
        "segments_postprocess_fallback": 0,
    }
    summary.update(summary_overrides)
    return {"summary": summary}


def test_clean_report_passes():
    verdict = evaluate(_report())
    assert verdict.status == "pass"
    assert verdict.reasons == []
    assert verdict.passed is True


def test_empty_report_passes_honestly_not_fails_silently():
    """Video chưa từng render (không có summary) -> "pass" trung thực
    (không có gì để đánh giá), KHÔNG phải fail ngầm định."""
    assert evaluate({}).status == "pass"
    assert evaluate({"summary": {}}).status == "pass"


def test_issues_under_every_threshold_warns_not_fails():
    report = _report(segments_ok=98, segments_over_budget=2)  # 2% < 15% ngưỡng
    verdict = evaluate(report)
    assert verdict.status == "warn"
    assert verdict.passed is True
    assert "2/100" in verdict.reasons[0]


def test_over_budget_ratio_above_threshold_fails():
    report = _report(segments_ok=70, segments_over_budget=30)  # 30% > 15%
    thresholds = QualityThresholds(max_over_budget_ratio=0.15)
    verdict = evaluate(report, thresholds)
    assert verdict.status == "fail"
    assert verdict.passed is False
    assert "vượt ngân sách" in verdict.reasons[0]


def test_speed_fallback_ratio_above_threshold_fails():
    report = _report(segments_ok=80, segments_speed_fallback=20)  # 20% > 10%
    verdict = evaluate(report, QualityThresholds(max_speed_fallback_ratio=0.10))
    assert verdict.status == "fail"
    assert any("dự phòng tốc độ" in r for r in verdict.reasons)


def test_postprocess_fallback_ratio_above_threshold_fails():
    report = _report(segments_ok=80, segments_postprocess_fallback=20)
    verdict = evaluate(report, QualityThresholds(max_postprocess_fallback_ratio=0.10))
    assert verdict.status == "fail"
    assert any("dự phòng hậu kỳ" in r for r in verdict.reasons)


def test_max_shift_above_threshold_fails():
    report = _report(max_shift_s=2.5)
    verdict = evaluate(report, QualityThresholds(max_shift_s=1.0))
    assert verdict.status == "fail"
    assert any("lệch timeline" in r for r in verdict.reasons)


def test_multiple_breaches_all_listed_as_reasons():
    report = _report(segments_ok=50, segments_over_budget=30,
                     segments_speed_fallback=20, max_shift_s=3.0)
    verdict = evaluate(report, QualityThresholds(
        max_over_budget_ratio=0.15, max_speed_fallback_ratio=0.10, max_shift_s=1.0))
    assert verdict.status == "fail"
    assert len(verdict.reasons) == 3


def test_exactly_at_threshold_does_not_fail():
    """Ngưỡng là CHẶN TRÊN — đúng bằng ngưỡng không bị coi là vượt."""
    report = _report(segments_ok=85, segments_over_budget=15)  # đúng 15%
    verdict = evaluate(report, QualityThresholds(max_over_budget_ratio=0.15))
    assert verdict.status != "fail"


def test_from_settings_reads_configured_thresholds():
    from autodub.config import Settings

    settings = Settings()
    settings.quality_gate_max_over_budget_ratio = 0.5
    settings.quality_gate_max_speed_fallback_ratio = 0.5
    settings.quality_gate_max_postprocess_fallback_ratio = 0.5
    settings.quality_gate_max_shift_s = 9.0
    thresholds = QualityThresholds.from_settings(settings)
    assert thresholds.max_over_budget_ratio == 0.5
    assert thresholds.max_shift_s == 9.0


def test_to_dict_shape():
    verdict = evaluate(_report(segments_ok=70, segments_over_budget=30))
    d = verdict.to_dict()
    assert d["status"] == "fail"
    assert isinstance(d["reasons"], list) and d["reasons"]
