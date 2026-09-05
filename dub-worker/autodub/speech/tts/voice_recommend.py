"""Gợi ý giọng đọc theo nội dung video — mini-spec V33, docs/PLAN.md Phase G.

Đầu vào là ``voice_hint`` do LLM trả về ở lượt "phân tích ngữ cảnh video"
(Lượt 0, SaaS — xem ``control_server/src/prompts/translate.js::
ANALYSIS_SCHEMA``), dạng ``{"gender": "male"|"female"|"", "style":
"tu_nhien"|"tin_tuc"|"doc_truyen"|""}``.

Constraint 2 của mini-spec: KHÔNG suy đoán phong cách vượt quá dữ liệu THẬT
đang có trong catalog. ``Voice.style`` mặc định là ``"tu_nhien"`` cho MỌI
giọng — kể cả giọng không hề có tín hiệu phong cách thật (suy từ tên hiển
thị, xem ``voices.py::_STYLE_FROM_TEXT``). Vì "tu_nhien" vừa là giá trị mặc
định vừa là 1 style thật, không thể phân biệt "giọng này THẬT SỰ tự nhiên"
với "giọng này không có dữ liệu phong cách". Do đó module này chỉ coi
``style in {"tin_tuc", "doc_truyen"}`` là tín hiệu đáng tin (2 giá trị đó
CHỈ được gán khi tên giọng thật sự chứa từ khoá tương ứng) — "tu_nhien"/""
từ LLM KHÔNG được dùng để lọc/xếp hạng, vì đa số giọng sẽ "khớp" một cách
vô nghĩa.
"""
from __future__ import annotations

from dataclasses import dataclass

from autodub.speech.tts.voices import Voice

#: Giá trị style THẬT đáng tin để khớp — "tu_nhien" bị loại có chủ đích (xem
#: docstring module).
_TRUSTED_STYLES = ("tin_tuc", "doc_truyen")

_GENDER_LABEL = {"male": "giọng nam", "female": "giọng nữ"}
_STYLE_LABEL = {"tin_tuc": "phong cách tin tức", "doc_truyen": "phong cách kể chuyện"}


@dataclass(frozen=True)
class VoiceRecommendation:
    """Một giọng được đề xuất, kèm lý do đọc được (Constraint 4)."""

    voice: Voice
    reasons: tuple[str, ...]

    @property
    def reason_text(self) -> str:
        return ", ".join(self.reasons) if self.reasons else ""


def recommend_voices(voice_hint: dict | None, catalog: list[Voice],
                     n: int = 3) -> list[VoiceRecommendation]:
    """Đề xuất tối đa ``n`` giọng khớp ``voice_hint``, xếp hạng gần đúng nhất
    trước. Trả về RỖNG (không suy đoán) khi thiếu tín hiệu đáng tin.

    - ``gender`` là bộ lọc CỨNG khi có (male/female) — không đề xuất giọng
      sai giới tính dù có khớp phong cách.
    - ``style`` chỉ dùng khi là 1 trong 2 giá trị đáng tin
      (``tin_tuc``/``doc_truyen``) — xếp giọng khớp style lên trước trong
      số các giọng đã qua bộ lọc giới tính, KHÔNG loại giọng không khớp
      style (vì phần lớn giọng thiếu dữ liệu style thật, loại hết sẽ mất
      gần như toàn bộ catalog một cách vô căn cứ).
    """
    if not voice_hint or not catalog:
        return []

    gender = str(voice_hint.get("gender") or "").strip().lower()
    if gender not in ("male", "female"):
        gender = ""
    style = str(voice_hint.get("style") or "").strip().lower()
    if style not in _TRUSTED_STYLES:
        style = ""

    if not gender and not style:
        return []

    candidates = catalog
    if gender:
        candidates = [v for v in candidates if v.gender == gender]
    if not candidates:
        # Không có giọng nào khớp giới tính đề xuất — thà không gợi ý gì
        # còn hơn gợi ý sai giới tính (Constraint 5: gợi ý phải đáng tin).
        return []

    def _sort_key(v: Voice) -> tuple:
        style_match = 0 if (style and v.style == style) else 1
        return (style_match,)

    ranked = sorted(candidates, key=_sort_key)

    out = []
    for v in ranked[:max(0, n)]:
        reasons = []
        if gender:
            reasons.append(_GENDER_LABEL[gender])
        if style and v.style == style:
            reasons.append(_STYLE_LABEL[style])
        out.append(VoiceRecommendation(voice=v, reasons=tuple(reasons)))
    return out
