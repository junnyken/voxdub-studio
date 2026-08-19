"""Hộp thoại "Xem trước người nói" — mini-spec V26 Scope E (docs/PLAN.md
Phase G, gap còn lại ghi trong docs/TEST_LOG.md).

Diarization (V26) gắn `seg["speaker_label"]` cho từng câu; hộp thoại này cho
người dùng xem những người nói đã phát hiện được và đổi giọng theo TỪNG
người nói một lần, thay vì phải mở popup giọng cho từng câu lẻ. Chỉ là lớp
hiển thị — không tự ghi đĩa; nơi gọi (Trình chỉnh sửa) chịu trách nhiệm gọi
`autodub.editor.set_speaker_voice()` khi nhận tín hiệu `voice_changed`,
đúng như cách `SubtitleListPanel.voice_changed` đã làm cho từng câu.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.ui.buttons import GhostButton
from autodub_gui.voice_picker import VoicePicker

_DIALOG_MIN_W = 520
_DIALOG_MIN_H = 420


def _display_name(speaker_label: str) -> str:
    """"SPEAKER_00" -> "Người nói 1" — thân thiện hơn nhãn kỹ thuật của
    pyannote.audio."""
    try:
        n = int(speaker_label.rsplit("_", 1)[-1]) + 1
        return f"Người nói {n}"
    except (ValueError, IndexError):
        return speaker_label


class _SpeakerRow(QFrame):
    """Một người nói: tên hiển thị, số câu, câu mẫu, ô chọn giọng."""

    voice_changed = Signal(str, str)   # speaker_label, tên giọng
    name_requested = Signal(str, str)  # speaker_label, câu mẫu — V89

    def __init__(self, speaker: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = speaker["speaker_label"]
        self._sample = str(speaker.get("sample_text") or "")
        self.setStyleSheet(
            f"QFrame {{ background: {tokens.BG_PANEL}; "
            f"border: 1px solid {tokens.BORDER_DEFAULT}; "
            f"border-radius: {tokens.RADIUS_LG}px; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_3, tokens.SP_3,
                                tokens.SP_3, tokens.SP_3)
        root.setSpacing(tokens.SP_2)

        head = QHBoxLayout()
        title = QLabel(_display_name(self._label))
        title.setStyleSheet(
            f"color: {tokens.TEXT_PRIMARY}; font-size: {tokens.FS_BODY}px; "
            f"font-weight: 600; background: transparent;")
        head.addWidget(title)
        head.addStretch()
        count = QLabel(f"{speaker.get('segment_count', 0)} câu")
        count.setStyleSheet(
            f"color: {tokens.TEXT_MUTED}; font-size: {tokens.FS_META}px; "
            f"background: transparent;")
        head.addWidget(count)
        root.addLayout(head)
        self._title = title

        sample_text = speaker.get("sample_text") or ""
        if sample_text:
            sample = QLabel(f"“{sample_text}”")
            sample.setWordWrap(True)
            sample.setStyleSheet(
                f"color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FS_META}px; "
                f"font-style: italic; background: transparent;")
            root.addWidget(sample)

        # V89 — "Người nói 1/2/3" không giúp nhớ ai là ai khi dub cả series.
        # Trợ lý đọc chính lời họ nói rồi đề xuất tên gọi ngắn.
        if self._sample:
            self.btn_name = GhostButton("Gợi ý tên gọi")
            self.btn_name.setToolTip(
                "Nhờ trợ lý đọc lời của người này rồi đề xuất tên gọi ngắn, "
                "dễ nhớ. Cần tài khoản VoxDub.")
            self.btn_name.clicked.connect(
                lambda: self.name_requested.emit(self._label, self._sample))
            root.addWidget(self.btn_name)

        self.picker = VoicePicker("Giọng cho người nói này")
        if speaker.get("voice"):
            self.picker.set_voice(speaker["voice"])
        self.picker.changed.connect(
            lambda: self.voice_changed.emit(self._label, self.picker.voice()))
        root.addWidget(self.picker)


def _dat_ten_goi_y(row, ten: str, ly_do: str) -> None:
    """Hiện tên trợ lý đề xuất ngay trên tiêu đề hàng.

    KHÔNG ghi vào hồ sơ: hồ sơ nhân vật là thứ áp cho mọi tập sau, đặt nhầm
    còn phiền hơn để nguyên "Người nói 2". Đây chỉ là gợi ý để người dùng đọc
    rồi tự gõ vào trang Hồ sơ nhân vật.
    """
    goc = _display_name(row._label)
    row._title.setText(f"{goc} — {ten}")
    if ly_do:
        row._title.setToolTip(f"Trợ lý đề xuất vì: {ly_do}")


class SpeakerPreviewDialog(QDialog):
    """Xem trước & đổi giọng theo từng người nói phát hiện bởi diarization.

    Chỉ hiển thị + phát tín hiệu, KHÔNG tự đọc/ghi đĩa — nơi gọi phải nối
    ``voice_changed`` với ``autodub.editor.set_speaker_voice()`` (giống mọi
    thao tác voice khác trong Trình chỉnh sửa).
    """

    voice_changed = Signal(str, str)   # speaker_label, tên giọng
    name_requested = Signal(str, str)  # speaker_label, câu mẫu — V89

    def show_name(self, speaker_label: str, ten: str, ly_do: str = "") -> None:
        """Hiện tên trợ lý đề xuất cho một người nói (V89)."""
        row = self._rows.get(speaker_label)
        if row is not None and ten:
            _dat_ten_goi_y(row, ten, ly_do)

    def __init__(self, speakers: list[dict], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Xem trước người nói")
        self.setModal(True)
        self.setMinimumSize(_DIALOG_MIN_W, _DIALOG_MIN_H)

        self._rows: dict[str, _SpeakerRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_5, tokens.SP_5,
                                tokens.SP_5, tokens.SP_5)
        root.setSpacing(tokens.SP_3)

        intro = QLabel(
            "VoxDub phát hiện các người nói khác nhau trong video này. "
            "Đổi giọng ở đây sẽ áp dụng cho MỌI câu của người nói đó — bấm "
            "«Lưu tất cả và đọc lại» ở mục Giọng đọc sau khi đổi.")
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FS_BODY}px; "
            f"background: transparent;")
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setSpacing(tokens.SP_3)
        for speaker in speakers:
            row = _SpeakerRow(speaker)
            row.voice_changed.connect(self.voice_changed.emit)
            row.name_requested.connect(self.name_requested.emit)
            self._rows[speaker["speaker_label"]] = row
            col.addWidget(row)
        col.addStretch()
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = GhostButton("Đóng")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)
