"""Ô chọn ngôn ngữ FLORES-200 dùng chung.

Tách ra từ trang Dịch phụ đề rời (mini-spec V14) để dùng lại ở bất kỳ nơi
nào cần chọn một ngôn ngữ NGUỒN bất kỳ trong ~200 mã — khác `DUB_TARGETS`
(10 ngôn ngữ ĐÍCH lồng tiếng, hẹp và đã đăng ký giọng đọc), nơi phụ đề nhập
vào có thể ở BẤT KỲ ngôn ngữ nào, không giới hạn theo `SOURCE_LANG_MAP` hẹp
của pipeline dub (xem Constraint 1 của V14, docs/PLAN.md).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from autodub_gui.ui.inputs import LabeledCombo


def language_options() -> list[tuple[str, str]]:
    from autodub.text.flores200 import FLORES200_LANGUAGES

    return sorted(((name, code) for code, name in FLORES200_LANGUAGES.items()),
                  key=lambda pair: pair[0])


def make_searchable(combo: LabeledCombo) -> None:
    """Cho gõ để lọc trong ~200 mục — QComboBox editable + QCompleter (mẫu
    Qt chuẩn), không đổi cách chọn bằng chuột hay `current_key()`."""
    box = combo.combo
    box.setEditable(True)
    box.setInsertPolicy(box.InsertPolicy.NoInsert)
    completer = QCompleter(box.model(), box)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    box.setCompleter(completer)
