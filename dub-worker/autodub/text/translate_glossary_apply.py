"""Áp glossary hậu xử lý cho nhánh dịch LOCAL (NLLB) — mini-spec V27
(docs/PLAN.md, Phase G).

Bug thật đã audit: `translate_glossary` (Settings) chỉ được enforce ở nhánh
SaaS (`translate_hint.py::build_user_context_block`, chèn vào prompt LLM) —
nhánh local NLLB (`translate_local_worker.py`) không nhận prompt (seq2seq
thuần, không phải mô hình theo chỉ dẫn) nên KHÔNG BAO GIỜ đọc glossary.
`ctranslate2.Translator.translate_batch()`'s ``target_prefix`` chỉ ép token
ngôn ngữ đích ở đầu chuỗi — không có API lexical-constraint để ép 1 từ giữa
câu (đã audit, xem docs/PLAN.md mục V26-V31 "Audit Before Build" chung).
Cơ chế khả thi DUY NHẤT: hậu xử lý tìm-thay-thế.

Giới hạn kỹ thuật CHỦ ĐÍCH KHÔNG che giấu: tìm-thay-thế văn bản không xử lý
biến cách/chia động từ/thứ tự từ — chỉ đảm bảo thuật ngữ XUẤT HIỆN đúng,
không đảm bảo ngữ pháp tự nhiên quanh nó (khác nhánh SaaS, LLM tự nhiên hoá
câu quanh thuật ngữ khoá).
"""
from __future__ import annotations

import re

#: "gốc = dịch" mỗi dòng — đúng định dạng đã ghi trong config.py
#: (``translate_glossary: str = ""  # thuật ngữ cố định, mỗi dòng "gốc = dịch"``).
_LINE_RE = re.compile(r"^(.+?)=(.+)$")

#: Ký tự CJK — không có "ranh giới từ" (\b không hoạt động đúng, đúng bài
#: học V19: dùng \s* không \s+ cho CJK). Dò 1 ký tự CJK trong thuật ngữ để
#: chọn nhánh so khớp phù hợp.
_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힣]")


def parse_glossary(raw: str) -> list[tuple[str, str]]:
    """"gốc = dịch" mỗi dòng → [(gốc, dịch), ...]. Dòng rỗng/không có "="
    bị bỏ qua (không lỗi — glossary do người dùng tự gõ tay, dòng lỗi định
    dạng không được làm hỏng cả danh sách)."""
    pairs: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        source, target = m.group(1).strip(), m.group(2).strip()
        if source and target:
            pairs.append((source, target))
    return pairs


def _is_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def apply_glossary(source_text: str, translated_text: str,
                   glossary_pairs: list[tuple[str, str]]) -> str:
    """Ép thuật ngữ đích vào bản dịch NẾU thuật ngữ nguồn có mặt trong câu
    gốc mà thuật ngữ đích CHƯA có sẵn trong bản dịch (tránh thay khi NLLB
    tình cờ đã dịch đúng — không thay 2 lần).

    Không match nhầm giữa-từ: dùng ranh giới từ (``\\b``) cho ngôn ngữ có
    khoảng trắng (Latin); dò CJK trực tiếp (không có khái niệm ranh giới từ
    rõ ràng cho CJK).
    """
    result = translated_text
    for source_term, target_term in glossary_pairs:
        if not source_term or source_term.lower() not in source_text.lower():
            continue
        if target_term in result:
            continue  # NLLB tình cờ đã dịch đúng — không thay 2 lần
        if _is_cjk(target_term):
            # Không có ranh giới từ cho CJK — chèn thêm vào cuối câu dịch,
            # đơn giản và an toàn hơn cố đoán vị trí chèn giữa câu.
            result = f"{result} ({target_term})"
        else:
            pattern = re.compile(r"\b" + re.escape(source_term) + r"\b",
                                 re.IGNORECASE)
            if pattern.search(result):
                # Bản dịch giữ nguyên thuật ngữ nguồn (NLLB không dịch tên
                # riêng) — thay đúng ranh giới từ.
                result = pattern.sub(target_term, result, count=1)
            else:
                # Thuật ngữ nguồn không xuất hiện dạng nguyên văn trong bản
                # dịch (đã bị dịch thành từ khác) — chèn thêm để đảm bảo
                # thuật ngữ đích CÓ MẶT, đúng Success Criteria của V27
                # ("xuất hiện đúng", không yêu cầu ngữ pháp hoàn hảo).
                result = f"{result} ({target_term})"
    return result
