"""Gán giọng TTS cho từng người nói phát hiện được — round-robin trên danh
mục giọng khả dụng. Mini-spec V26 (docs/PLAN.md, Phase G).

Tách khỏi :mod:`autodub.speech.diarization` để module diarization không cần
biết gì về danh mục giọng (``voices.catalog()``) — driver diarization chỉ lo
tách người nói theo thời gian, module này lo "người nói này đọc giọng nào".
"""
from __future__ import annotations


def assign_voices_round_robin(
    speaker_labels: list[str], available_voice_names: list[str],
) -> dict[str, str]:
    """Gán 1 tên giọng cho từng nhãn người nói, round-robin qua danh mục.

    ``speaker_labels``: nhãn DUY NHẤT (không lặp), theo thứ tự bất kỳ.
    ``available_voice_names``: tên giọng khả dụng (PHẢI không rỗng).

    Số người nói phát hiện được VƯỢT số giọng khả dụng → vòng lại từ đầu
    (Constraint 4 của V26: xử lý rõ ràng, không crash) — 2 người nói có thể
    dùng chung 1 giọng khi catalog quá ít.
    """
    if not available_voice_names:
        raise ValueError("Danh mục giọng rỗng — không gán được")
    return {
        label: available_voice_names[i % len(available_voice_names)]
        for i, label in enumerate(speaker_labels)
    }


def apply_segment_voices(
    asr_segments: list[dict], voice_map: dict[str, str],
) -> None:
    """Ghi ``seg["voice"]`` cho từng segment có ``speaker_label`` theo
    ``voice_map`` — TÁI DÙNG cơ chế multi-voice per-segment đã có sẵn từ
    trước V26 (``pipeline.py`` đọc ``seg["voice"]`` tuỳ chọn, trước đây chỉ
    gán tay qua editor). Sửa TRỰC TIẾP ``asr_segments``.

    Segment không có ``speaker_label`` (diarization bỏ sót, hoặc tính năng
    tắt) giữ NGUYÊN — không set ``seg["voice"]``, pipeline tự dùng giọng mặc
    định toàn video như hành vi trước V26 (0 regression).
    """
    for seg in asr_segments:
        label = seg.get("speaker_label")
        if label and label in voice_map:
            seg["voice"] = voice_map[label]
