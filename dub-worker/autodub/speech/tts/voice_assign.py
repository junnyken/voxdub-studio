"""Gán giọng TTS cho từng người nói phát hiện được. Mini-spec V26 (round-
robin thuần) → V36 (docs/PLAN.md, Phase G — gán theo giới tính ước lượng
từ pitch khi có, round-robin làm lối thoát an toàn khi không chắc).

Tách khỏi :mod:`autodub.speech.diarization` để module diarization không cần
biết gì về danh mục giọng (``voices.catalog()``) — driver diarization chỉ lo
tách người nói theo thời gian, module này lo "người nói này đọc giọng nào".
"""
from __future__ import annotations

from autodub.speech.tts.voices import Voice


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


def assign_voices_by_gender(
    speaker_labels: list[str], genders: dict[str, str],
    catalog: list[Voice], fallback_names: list[str],
) -> dict[str, str]:
    """Gán giọng theo giới tính ước lượng (mini-spec V36) — người nói có
    giới tính ước lượng được (``genders[label]`` là ``"male"``/``"female"``)
    nhận 1 giọng CÙNG giới tính từ ``catalog`` (round-robin TRONG NHÓM giới
    tính đó nếu nhiều người nói cùng giới tính khớp cùng lúc).

    Người nói KHÔNG ước lượng được giới tính (``genders`` thiếu nhãn, hoặc
    giá trị rỗng — vùng mù mờ, xem `diarization_voice_match.py`) HOẶC
    catalog không có giọng nào đúng giới tính đó → rơi về
    :func:`assign_voices_round_robin` nguyên bản trên ``fallback_names``
    (Constraint 2/6 của V36: không đoán liều, luôn gán được 1 giọng nào
    đó chứ không bỏ sót người nói).
    """
    by_gender: dict[str, list[str]] = {"male": [], "female": []}
    for v in catalog:
        if v.gender in by_gender:
            by_gender[v.gender].append(v.name)

    voice_map: dict[str, str] = {}
    unresolved: list[str] = []
    cursor = {"male": 0, "female": 0}
    for label in speaker_labels:
        names = by_gender.get(genders.get(label, ""))
        if not names:
            unresolved.append(label)
            continue
        voice_map[label] = names[cursor[genders[label]] % len(names)]
        cursor[genders[label]] += 1

    if unresolved:
        voice_map.update(assign_voices_round_robin(unresolved, fallback_names))
    return voice_map
