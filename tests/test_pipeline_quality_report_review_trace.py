"""Mini-spec V29 (docs/PLAN.md, Phase G) — field `translate_review` mới
trong `quality_report.json`, sinh bởi
`DubPipeline._build_quality_report(..., review_trace=...)`.
"""
from __future__ import annotations

from autodub.languages import get_target
from autodub.pipeline import DubPipeline


def test_review_trace_defaults_to_empty_list_0_regression():
    """Không truyền review_trace (giữ nguyên caller cũ nào khác nếu có) ->
    field vẫn tồn tại nhưng rỗng — không lỗi, không đổi shape summary/
    per_segment đã có từ V23."""
    target = get_target("vi")
    segments = [{"id": 1, "text_vi": "Xin chào.", "start": 0.0, "duration": 5.0}]
    report = DubPipeline._build_quality_report(target, segments, {}, None)
    assert report["translate_review"] == []
    assert "summary" in report and "per_segment" in report  # 0 regression V23


def test_review_trace_surfaces_in_report():
    target = get_target("vi")
    segments = [{"id": 1, "text_vi": "Xin chào.", "start": 0.0, "duration": 5.0}]
    trace = [{"id": 1, "reason": "too_short", "before": "Ngắn.",
             "after": "Xin chào.", "improved": True}]
    report = DubPipeline._build_quality_report(target, segments, {}, None,
                                                review_trace=trace)
    assert report["translate_review"] == trace


def test_review_trace_none_normalizes_to_empty_list():
    target = get_target("vi")
    segments = [{"id": 1, "text_vi": "Xin chào.", "start": 0.0, "duration": 5.0}]
    report = DubPipeline._build_quality_report(target, segments, {}, None,
                                                review_trace=None)
    assert report["translate_review"] == []


def test_summary_and_per_segment_unaffected_by_review_trace_additive_only():
    """Constraint 2: review_trace CHỈ thêm field mới, không đụng
    summary/per_segment đã có."""
    target = get_target("vi")
    segments = [{"id": 1, "text_vi": "Xin chào.", "start": 0.0, "duration": 5.0}]
    without = DubPipeline._build_quality_report(target, segments, {}, None)
    with_trace = DubPipeline._build_quality_report(
        target, segments, {}, None,
        review_trace=[{"id": 1, "reason": "cjk", "before": "a", "after": "b",
                       "improved": True}])
    assert without["summary"] == with_trace["summary"]
    assert without["per_segment"] == with_trace["per_segment"]
