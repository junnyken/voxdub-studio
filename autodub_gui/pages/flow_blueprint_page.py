"""Trang Phân tích cấu trúc video tham khảo — mini-spec H2 (docs/PLAN.md,
Phase H "Viral Flow Clone & Brand Rewrite").

Wording bắt buộc (Guardrail của H2): LUÔN nói "phân tích cấu trúc video tham
khảo", KHÔNG BAO GIỜ nói "copy/sao chép video viral" — công cụ này đọc VAI
TRÒ KỂ CHUYỆN từng đoạn (mở hook, bằng chứng, cao trào, kêu gọi hành động…),
không lấy nguyên văn lời thoại/caption của video nguồn.

Hai giai đoạn: (1) `FlowBlueprintWorker` chạy local (tải video → chép lời →
đọc caption) rồi gọi máy chủ phân tích — nặng, xem `autodub/flow_blueprint.py`;
(2) `FlowBlueprintCrudWorker` cho danh sách/xoá các lượt đã lưu — mỏng, cùng
khuôn `BrandProfileWorker` (H1).

Hiển thị tiến độ bằng MÔ TẢ BƯỚC THẬT + giây đã chạy (C68: không bịa % hoàn
thành khi không đo được) — cùng cách `TranscribePage`/log_text.py đã làm cho
lượt tách nhạc cloud (V12).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from autodub_gui import icons, tokens
from autodub_gui.log_text import error_line
from autodub_gui.pages import BasePage
from autodub_gui.ui.buttons import GhostButton, IconButton, PrimaryButton, SecondaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.inputs import LabeledLineEdit
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.table import Column, DataTable
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import FlowBlueprintCrudWorker, FlowBlueprintWorker

_ACTION_ICON = 28
_PAGE_MARGIN = 28

_MEDIA_FILTER = ("Video (*.mp4 *.mkv *.mov *.avi *.webm);;Tất cả (*.*)")

#: Nhãn tiếng Việt cho vocabulary ĐÓNG của beat_type (khớp
#: `control_server/src/models/FlowBlueprint.js::BEAT_TYPES`) — người dùng
#: không cần biết tên tiếng Anh bên trong.
_BEAT_TYPE_LABELS = {
    "hook": "Mở hook",
    "problem_context": "Nêu vấn đề",
    "tension": "Tăng kịch tính",
    "proof": "Bằng chứng",
    "demonstration": "Trình diễn",
    "payoff": "Cao trào / kết quả",
    "twist": "Bất ngờ",
    "objection": "Giải đáp phản bác",
    "cta": "Kêu gọi hành động",
    "transition": "Chuyển đoạn",
    "unknown": "Chưa xác định",
}

#: Ghi chú tình trạng bằng chứng cho từng beat — wording đúng như Scope E của
#: H2: KHÔNG BAO GIỜ nói "video không có caption" (video có thể có caption ở
#: đoạn KHÁC), và "unconfirmed" phải nói rõ lý do OCR tiếng Việt không đáng tin.
_EVIDENCE_STATUS_NOTES = {
    # `ok` từng KHÔNG có ở đây, nên cột này luôn rỗng — và vì máy chủ cũng
    # chưa từng ghi trường `evidenceStatus`, mọi đoạn đều là `ok`. Hai lỗi
    # che nhau: cột rỗng trông như "chưa có gì để nói", trong khi thật ra
    # không đoạn nào được chấm cả.
    "ok": "Đọc được chữ trên hình ở đoạn này.",
    "unconfirmed": "Cần bạn xác nhận — OCR tiếng Việt có thể thiếu dấu/sai ký tự.",
    "unavailable": "Không đọc được caption overlay ở đoạn này — xem ghi chú "
                   "bằng chứng phía trên.",
    "failed": "Đọc chữ overlay bị lỗi kỹ thuật ở đoạn này.",
    "no_text": "Không có chữ overlay ở đoạn này.",
}


def _giay_thanh_mm_ss(giay: float) -> str:
    giay = max(0, int(round(giay)))
    return f"{giay // 60}:{giay % 60:02d}"


class FlowBlueprintPage(BasePage):
    """Phân tích cấu trúc MỘT video tham khảo, xem lại/xoá các lượt đã lưu."""

    #: Lối vào mini-spec H3. Trang «Viết kịch bản» KHÔNG nằm trên thanh bên
    #: (đã kín ở màn 1080p) và cũng không nên nằm đó: chưa phân tích nhịp thì
    #: chưa viết kịch bản được, nên lối vào đúng chỗ là ngay sau kết quả này.
    brand_script_requested = Signal()

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: FlowBlueprintWorker | None = None
        self._crud_worker: FlowBlueprintCrudWorker | None = None
        self._history: list[dict] = []
        self._elapsed = QTimer(self)
        self._elapsed.setInterval(1000)
        self._elapsed.timeout.connect(self._tick_elapsed)
        self._elapsed_s = 0
        self._current_phase_text = ""
        self._build()

    # ------------------------------------------------------------ dựng UI --
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        card = Card(padding=tokens.SP_4)
        card.add_header("Phân tích cấu trúc video tham khảo")

        hint = QLabel(
            "Đọc VAI TRÒ KỂ CHUYỆN của từng đoạn trong một video tham khảo — "
            "mở hook, nêu vấn đề, bằng chứng, cao trào, kêu gọi hành động… — "
            "để bạn hiểu NHỊP KỂ CHUYỆN, không lấy nguyên văn lời thoại hay "
            "caption của video nguồn. Không dùng để sao chép video của người khác.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        card.body.addWidget(hint)

        self.source = LabeledLineEdit(
            "Liên kết hoặc file video", "https://… hoặc D:\\video\\tham-khao.mp4",
            "Dán liên kết video, hoặc bấm «Chọn file…» để lấy file trên máy.")
        card.body.addWidget(self.source)

        chon = QHBoxLayout()
        chon.setSpacing(tokens.SP_2)
        self.btn_pick = SecondaryButton("Chọn file…")
        self.btn_pick.clicked.connect(self._pick_file)
        chon.addWidget(self.btn_pick)
        chon.addStretch()
        card.body.addLayout(chon)

        cost_hint = QLabel(
            "Chi phí gồm HAI phần: 8 Vox cho lượt phân tích cấu trúc, cộng "
            "8 Vox cho mỗi lô 6 khung hình phải nhờ máy chủ đọc chữ có dấu. "
            "Video ~60 giây thường có khoảng 15 caption khác nhau ⇒ 3 lô ⇒ "
            "tổng khoảng 32 Vox. Trừ SAU KHI chạy xong. Video dài hơn 90 giây "
            "vẫn chạy được nhưng đoạn giữa có thể bỏ sót vài caption chớp "
            "nhanh, và càng nhiều caption khác nhau thì càng nhiều lô.")
        cost_hint.setObjectName("hint")
        cost_hint.setWordWrap(True)
        card.body.addWidget(cost_hint)

        root.addWidget(card)

        hanh_dong = QHBoxLayout()
        hanh_dong.setSpacing(tokens.SP_3)
        self.btn_run = PrimaryButton("Phân tích cấu trúc")
        self.btn_run.clicked.connect(self._run)
        hanh_dong.addWidget(self.btn_run)
        self.btn_stop = SecondaryButton("Dừng")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        hanh_dong.addWidget(self.btn_stop)
        hanh_dong.addStretch()
        self.btn_brand_script = SecondaryButton("Viết kịch bản cho thương hiệu…")
        self.btn_brand_script.clicked.connect(self.brand_script_requested.emit)
        hanh_dong.addWidget(self.btn_brand_script)
        root.addLayout(hanh_dong)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        self.log = LogPanel()
        self.log.setMaximumHeight(100)
        root.addWidget(self.log)

        self.evidence_banner = QLabel("")
        self.evidence_banner.setObjectName("hint")
        self.evidence_banner.setWordWrap(True)
        self.evidence_banner.hide()
        root.addWidget(self.evidence_banner)

        self.beats_table = DataTable(
            [Column("Thời gian", width=90),
             Column("Vai trò kể chuyện", width=160),
             Column("Mô tả (trừu tượng)", stretch=True),
             Column("Tình trạng bằng chứng", stretch=True)],
            empty_title="Chưa có kết quả phân tích",
            empty_description="Dán liên kết hoặc chọn file rồi bấm «Phân tích cấu trúc».")
        root.addWidget(self.beats_table, 1)

        history_header = QHBoxLayout()
        history_title = QLabel("Đã phân tích trước đây")
        history_title.setObjectName("sectionTitle")
        history_header.addWidget(history_title)
        history_header.addStretch()
        self.btn_reload_history = GhostButton("Tải lại")
        self.btn_reload_history.clicked.connect(self._reload_history)
        history_header.addWidget(self.btn_reload_history)
        root.addLayout(history_header)

        self.history_table = DataTable(
            [Column("Nguồn", stretch=True),
             Column("Trạng thái", width=110),
             Column("Số đoạn", width=80),
             Column("Thao tác", width=90)],
            empty_title="Chưa phân tích video nào",
            empty_description="Các lượt đã phân tích sẽ hiện ở đây, dùng lại được nhiều lần.")
        self.history_table.setMaximumHeight(200)
        root.addWidget(self.history_table)

    # -- Vòng đời ---------------------------------------------------------
    def on_shown(self) -> None:
        self._reload_history()

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def shutdown(self) -> None:
        self._elapsed.stop()
        if self.is_running():
            self._worker.wait(5000)
        if self._crud_worker is not None and self._crud_worker.isRunning():
            self._crud_worker.wait(5000)

    # -- Chọn nguồn ---------------------------------------------------------
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video tham khảo", "", _MEDIA_FILTER)
        if path:
            self.source.set_text(path)

    # -- Chạy phân tích -------------------------------------------------------
    def _run(self) -> None:
        if self.is_running():
            TOASTS.warn("Đang phân tích — chờ lượt này xong đã.")
            return
        source = self.source.text().strip()
        if not source:
            TOASTS.warn("Dán liên kết hoặc chọn file video trước đã.")
            return
        from autodub.transcribe_tool import is_url

        if not is_url(source) and not os.path.isfile(source):
            TOASTS.warn(f"Không tìm thấy file: {source}")
            return

        settings = self._settings_provider()
        work_dir = os.path.join(str(getattr(settings, "output_dir", "") or "."),
                                "flow_blueprint")

        self.log.setPlainText("")
        self.evidence_banner.hide()
        self.beats_table.clear_rows()
        self.beats_table.auto_state()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._elapsed_s = 0
        self._elapsed.start()
        self._current_phase_text = "Đang chuẩn bị…"
        self.status.setText(self._current_phase_text)

        worker = FlowBlueprintWorker(source, work_dir, settings, parent=self)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _stop(self) -> None:
        if self.is_running():
            self._worker.cancel()
            self.btn_stop.setEnabled(False)
            self.status.setText("Đang dừng…")

    def _on_progress(self, step: str, detail: str) -> None:
        self._current_phase_text = detail or step
        self._tick_elapsed()

    def _tick_elapsed(self) -> None:
        # C68 — thời gian ĐÃ CHẠY THẬT, không phải % ước lượng không có cơ sở.
        self._elapsed_s += 1 if self._elapsed.isActive() else 0
        self.status.setText(f"{self._current_phase_text} (đã chạy {self._elapsed_s}s)")

    def _stop_elapsed(self) -> None:
        self._elapsed.stop()

    def _on_done(self, ket: dict) -> None:
        self._stop_elapsed()
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._render_beats(ket)
        TOASTS.success(f"Phân tích xong: {len(ket.get('beats') or [])} đoạn.")
        self._reload_history()

    def _on_failed(self, message: str) -> None:
        self._stop_elapsed()
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status.setText(f"Không phân tích được: {message}")
        text, level = error_line(message)
        self.log.append_log(text, level)
        TOASTS.warn("Phân tích thất bại — xem chi tiết bên dưới.")

    # -- Hiển thị kết quả ------------------------------------------------
    def _render_beats(self, ket: dict) -> None:
        evidence_summary = str(ket.get("evidenceSummary") or "")
        if evidence_summary:
            self.evidence_banner.setText(f"Bằng chứng: {evidence_summary}")
            self.evidence_banner.show()
        else:
            self.evidence_banner.hide()

        self.beats_table.clear_rows()
        for beat in ket.get("beats") or []:
            row = self.beats_table.add_row()
            start_s = float(beat.get("startS") or 0)
            end_s = float(beat.get("endS") or 0)
            self.beats_table.set_widget(
                row, 0, QLabel(f"{_giay_thanh_mm_ss(start_s)}–{_giay_thanh_mm_ss(end_s)}"))
            beat_type = str(beat.get("beatType") or "unknown")
            self.beats_table.set_widget(
                row, 1, QLabel(_BEAT_TYPE_LABELS.get(beat_type, beat_type)))
            mo_ta = " · ".join(
                v for v in (
                    str(beat.get("narrativeFunctionVi") or "").strip(),
                    str(beat.get("pacingNoteVi") or "").strip(),
                ) if v)
            mo_ta_label = QLabel(mo_ta)
            mo_ta_label.setWordWrap(True)
            self.beats_table.set_widget(row, 2, mo_ta_label)
            trang_thai = str(beat.get("evidenceStatus") or "ok")
            ghi_chu = _EVIDENCE_STATUS_NOTES.get(trang_thai, "")
            ghi_chu_label = QLabel(ghi_chu)
            ghi_chu_label.setWordWrap(True)
            self.beats_table.set_widget(row, 3, ghi_chu_label)
        self.beats_table.auto_state()

    # -- Lịch sử -------------------------------------------------------------
    def _reload_history(self) -> None:
        if self._crud_worker is not None and self._crud_worker.isRunning():
            return
        self.btn_reload_history.set_loading(True, "Đang tải…")
        worker = FlowBlueprintCrudWorker("list", parent=self)
        worker.finished_ok.connect(self._on_crud_ok)
        worker.failed.connect(self._on_crud_failed)
        worker.finished.connect(lambda: self.btn_reload_history.set_loading(False))
        self._crud_worker = worker
        worker.start()

    def _on_crud_ok(self, action: str, ket) -> None:
        if action == "list":
            self._history = ket or []
            self._render_history()
        elif action == "delete":
            TOASTS.success("Đã xoá lượt phân tích.")
            self._reload_history()

    def _on_crud_failed(self, action: str, message: str) -> None:
        if action == "list":
            # Thiếu lịch sử chỉ chặn bảng này, không chặn lượt phân tích mới —
            # cùng nguyên tắc `list_brand_profiles()`.
            self.log.append_log(f"Không tải được lịch sử: {message}", 30)
            return
        text, level = error_line(message)
        self.log.append_log(text, level)
        # "Thử lại sau" là lời khuyên SAI cho phần lớn nguyên nhân: hết hạn
        # đăng nhập hay thiết bị bị khoá thì thử lại bao nhiêu lần cũng vậy.
        from autodub_gui.dub_constants import friendly_server_error

        ConfirmDialog.show_error(self, "Không xoá được",
                                 friendly_server_error(message), detail=message)

    def _render_history(self) -> None:
        self.history_table.clear_rows()
        for bp in self._history:
            row = self.history_table.add_row()
            nguon = QLabel(str(bp.get("sourceReference") or ""))
            nguon.setWordWrap(True)
            self.history_table.set_widget(row, 0, nguon)
            self.history_table.set_widget(row, 1, QLabel(str(bp.get("status") or "")))
            self.history_table.set_widget(
                row, 2, QLabel(str(len(bp.get("beats") or []))))
            self.history_table.set_widgets(row, 3, self._history_actions(bp))
        self.history_table.auto_state()

    def _history_actions(self, bp: dict) -> list[QWidget]:
        view = IconButton(icons.external(tokens.TEXT_SECONDARY), "Xem lại",
                          size=_ACTION_ICON)
        view.clicked.connect(lambda _c=False, b=bp: self._render_beats(b))
        delete = IconButton(icons.trash(tokens.DANGER), "Xoá",
                            size=_ACTION_ICON)
        delete.clicked.connect(lambda _c=False, b=bp: self._on_delete_history(b))
        return [view, delete]

    def _on_delete_history(self, bp: dict) -> None:
        confirmed, _ = ConfirmDialog.ask(
            self, "Xoá lượt phân tích?",
            f"Xoá kết quả phân tích của «{bp.get('sourceReference', '')}»?",
            kind="warning", confirm_label="Xoá", cancel_label="Giữ lại")
        if not confirmed:
            return
        worker = FlowBlueprintCrudWorker("delete", blueprint_id=bp["id"], parent=self)
        worker.finished_ok.connect(self._on_crud_ok)
        worker.failed.connect(self._on_crud_failed)
        self._crud_worker = worker
        worker.start()
