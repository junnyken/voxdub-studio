"""Suy đoán giọng điệu 1 câu từ tín hiệu VĂN BẢN THUẦN (dấu câu, chữ hoa, từ
khoá cảm thán) — mini-spec V28 (docs/PLAN.md, Phase G), đường LOCAL-ONLY
(không có LLM phân tích ngữ cảnh).

Đây là ĐƯỜNG DỰ PHÒNG khi không có SaaS — ĐỘ CHÍNH XÁC THẤP HƠN HẲN so với
LLM đọc hiểu ngữ nghĩa cả câu (không suy đoán được mỉa mai, ẩn ý, ngữ cảnh
trước-sau). Constraint 2 của V28: gắn nhãn "thử nghiệm" khi hiển thị nguồn
tín hiệu này trong GUI, KHÔNG giả vờ ngang hàng phân tích LLM.

Áp dụng cho VĂN BẢN ĐÍCH (tiếng Việt, đã dịch) — VieNeu chỉ đọc tiếng Việt,
đây LÀ văn bản thật sự được tổng hợp giọng, không phải văn bản nguồn.
"""
from __future__ import annotations

#: 3 style THẬT của VieNeu (autodub/speech/tts/vieneu_worker.py --style
#: choices) — không bịa thêm giá trị nào ngoài những gì worker thật hỗ trợ.
VIENEU_STYLES = ("tu_nhien", "tin_tuc", "doc_truyen")

#: Từ khoá cảm thán tiếng Việt phổ biến — heuristic THÔ (khớp chuỗi con),
#: không phải NLP/phân tích ngữ nghĩa.
_EXCITED_WORDS = (
    "tuyệt vời", "quá đã", "không thể tin được", "trời ơi", "khủng khiếp",
    "kinh khủng", "tuyệt quá", "hay quá", "đỉnh quá",
)
_SERIOUS_WORDS = (
    "cảnh báo", "nghiêm trọng", "khẩn cấp", "chú ý", "lưu ý", "nguy hiểm",
)


def guess_tone(text: str) -> str:
    """"neutral" | "excited" | "serious" — heuristic THÔ dựa dấu câu + từ
    khoá. Câu rỗng/chỉ có dấu câu -> "neutral" (không suy đoán bừa)."""
    stripped = text.strip()
    if not stripped:
        return "neutral"
    lower = stripped.lower()

    if any(w in lower for w in _SERIOUS_WORDS):
        return "serious"
    if "!" in stripped or any(w in lower for w in _EXCITED_WORDS):
        return "excited"

    # Chữ hoa toàn bộ (viết hoa nhấn mạnh) — bỏ qua câu quá ngắn (dễ nhầm
    # từ viết tắt như "OK"/"TV") để tránh dương tính giả.
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) >= 6 and stripped == stripped.upper():
        return "excited"

    return "neutral"


#: tone -> style VieNeu thật. "excited" dùng doc_truyen (phong cách kể
#: chuyện, nhiều ngữ điệu lên xuống hơn tu_nhien); "serious" dùng tin_tuc
#: (phong cách tin tức, điềm tĩnh dứt khoát). Lựa chọn dựa trên MÔ TẢ style
#: đã có trong dự án (Settings VIENEU_STYLE), không suy đoán ngoài phạm vi
#: 3 giá trị worker thật hỗ trợ.
_TONE_TO_STYLE = {
    "neutral": "tu_nhien",
    "excited": "doc_truyen",
    "serious": "tin_tuc",
}


def tone_to_vieneu_style(tone: str) -> str:
    """tone -> style VieNeu thật — giá trị lạ rơi về "tu_nhien" (an toàn,
    không crash worker vì style không hợp lệ)."""
    return _TONE_TO_STYLE.get(tone, "tu_nhien")
