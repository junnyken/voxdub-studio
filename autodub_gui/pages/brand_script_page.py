"""Trang Viết kịch bản cho thương hiệu — mini-spec H3 (Phase H).

Lấy NHỊP KỂ CHUYỆN từ một lượt "Phân tích cấu trúc video tham khảo" (H2) và
HỒ SƠ THƯƠNG HIỆU (H1), rồi viết một kịch bản MỚI cho thương hiệu đó.

**Wording bắt buộc** (kế thừa guardrail H2): luôn nói "học nhịp kể chuyện",
KHÔNG BAO GIỜ nói "copy/sao chép video". Máy chủ chặn bằng mã chuyện kịch bản
trùng câu chữ nguồn — giao diện phải nói đúng như vậy, không hứa hơn.

**Nút "Dùng kịch bản này" chỉ sáng khi trạng thái là `ready`.** Không có nút
"bỏ qua cảnh báo, dùng luôn", và cũng không có đường vòng nào: trạng thái do
MÁY CHỦ tính, app chỉ hiển thị lại.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.status_text import STATUS_ERROR, STATUS_OK, STATUS_WARN
from autodub_gui.pages import BasePage
from autodub_gui.ui.buttons import GhostButton, PrimaryButton, SecondaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.table import Column, DataTable
from autodub_gui.ui.toast import TOASTS
from autodub_gui.workers import BrandProfileWorker, BrandScriptWorker, FlowBlueprintCrudWorker

_PAGE_MARGIN = 28

#: Nhãn tiếng Việt cho vocabulary beat_type — khớp `_BEAT_TYPE_LABELS` của
#: trang H2 (cùng nguồn: `models/FlowBlueprint.js::BEAT_TYPES`).
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

#: Bốn nguyên nhân "chưa kiểm được" — mỗi cái một câu RIÊNG. Gộp thành một
#: câu "chưa kiểm được" thì người dùng không biết mình có làm gì được không:
#: hai ca đầu là vô phương, hai ca sau thì chạy lại H2 là xong.
_LY_DO_CHUA_KIEM = {
    "khong_co_dau_van_tay":
        "Lượt phân tích video này chạy trước khi có bộ đối chiếu, nên không "
        "còn dữ liệu để kiểm. Phân tích lại video nguồn rồi tạo kịch bản mới.",
    "khac_phien_ban":
        "Bộ đối chiếu đã đổi kể từ lượt phân tích đó. Phân tích lại video "
        "nguồn để kiểm được.",
    "day_tran":
        "Video nguồn quá dài nên phần đối chiếu không phủ hết — không dám "
        "khẳng định đoạn này không trùng.",
    "bang_chung_khong_du":
        "Đoạn tương ứng trong video nguồn không đọc được lời hay chữ nào, "
        "nên không có gì để đối chiếu.",
}

_NHAN_TRANG_THAI = {
    "ready": "Dùng được",
    "blocked": "Bị chặn",
    "unconfirmed": "Chưa kiểm được",
    "draft": "Nháp",
    "checking": "Đang kiểm",
    "failed": "Hỏng",
}


def _nhan_beat(beat: dict) -> str:
    return _BEAT_TYPE_LABELS.get(str(beat.get("beatType") or ""), "Chưa xác định")


def _tom_tat_co(beat: dict) -> str:
    """Một dòng nói rõ đoạn này sạch hay bị chặn, và VÌ SAO.

    Không bao giờ chỉ trả "có vấn đề" — người dùng phải biết sửa ở đâu.
    """
    if beat.get("complianceFlag") == "violated":
        cum = beat.get("complianceExcerpt") or ""
        luat = beat.get("complianceRule") or ""
        return f"{STATUS_ERROR} Chứa cụm bạn đã cấm: «{cum}» (ràng buộc: «{luat}»)"
    if beat.get("originalityFlag") == "flagged":
        return (f"{STATUS_ERROR} Trùng câu chữ với video nguồn: «{beat.get('flaggedExcerpt') or ''}»"
                " — viết lại đoạn này")
    if beat.get("originalityFlag") == "unconfirmed":
        ly_do = _LY_DO_CHUA_KIEM.get(
            str(beat.get("lyDoChuaKiem") or ""), "Chưa đối chiếu được với video nguồn.")
        return f"{STATUS_WARN} Chưa kiểm được — {ly_do}"
    return f"{STATUS_OK} Không trùng câu chữ nguồn, không chứa cụm bị cấm"


class BrandScriptPage(BasePage):
    """Viết kịch bản cho thương hiệu từ nhịp kể chuyện đã phân tích."""

    #: Lối sang mini-spec H4 — dựng video từ kịch bản. Chỉ phát khi kịch bản
    #: đã `ready`, vì nút gọi nó chỉ sáng ở trạng thái đó.
    storyboard_requested = Signal(dict)

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: BrandScriptWorker | None = None
        self._bp_worker: FlowBlueprintCrudWorker | None = None
        self._brand_worker: BrandProfileWorker | None = None
        self._blueprints: list[dict] = []
        self._brands: list[dict] = []
        self._scripts: list[dict] = []
        self._hien_tai: dict | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        card = Card(padding=tokens.SP_4)
        card.add_header("Viết kịch bản cho thương hiệu")

        hint = QLabel(
            "Lấy NHỊP KỂ CHUYỆN từ một video tham khảo bạn đã phân tích, rồi "
            "viết một kịch bản MỚI cho thương hiệu của bạn — đúng giọng điệu, "
            "đúng điểm mạnh, tránh những gì bạn đã dặn là không được nói. "
            "Kịch bản sẽ được đối chiếu tự động với video nguồn: đoạn nào "
            "trùng câu chữ sẽ bị chặn, không có cách nào bỏ qua.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        card.body.addWidget(hint)

        chon = QHBoxLayout()
        chon.setSpacing(tokens.SP_3)
        self.cbo_blueprint = QComboBox()
        self.cbo_blueprint.setMinimumWidth(280)
        chon.addWidget(QLabel("Nhịp kể chuyện:"))
        chon.addWidget(self.cbo_blueprint, 1)
        self.cbo_brand = QComboBox()
        self.cbo_brand.setMinimumWidth(220)
        chon.addWidget(QLabel("Thương hiệu:"))
        chon.addWidget(self.cbo_brand, 1)
        card.body.addLayout(chon)

        cost_hint = QLabel(
            "Mỗi lượt viết tốn khoảng 12 Vox (giá khởi điểm) — trừ SAU KHI "
            "viết xong. Viết lại một đoạn cũng tính như một lượt.")
        cost_hint.setObjectName("hint")
        cost_hint.setWordWrap(True)
        card.body.addWidget(cost_hint)

        root.addWidget(card)

        hanh_dong = QHBoxLayout()
        hanh_dong.setSpacing(tokens.SP_3)
        self.btn_run = PrimaryButton("Viết kịch bản")
        self.btn_run.clicked.connect(self._run)
        hanh_dong.addWidget(self.btn_run)
        self.btn_reload = GhostButton("Tải lại danh sách")
        self.btn_reload.clicked.connect(self._reload_all)
        hanh_dong.addWidget(self.btn_reload)
        hanh_dong.addStretch()
        # Cửa sang H4. CHỈ sáng khi máy chủ trả `ready` — xem `_render_script`.
        self.btn_use = PrimaryButton("Dùng kịch bản này")
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self._use_script)
        hanh_dong.addWidget(self.btn_use)
        root.addLayout(hanh_dong)

        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.beats_table = DataTable(
            [Column("Đoạn", width=140),
             Column("Lời đọc", stretch=True),
             Column("Chữ trên hình", width=170),
             Column("Cần quay gì", stretch=True),
             Column("Kiểm tra", stretch=True),
             Column("", width=110)],
            empty_title="Chưa có kịch bản",
            empty_description="Chọn một nhịp kể chuyện và một thương hiệu rồi "
                              "bấm «Viết kịch bản».")
        root.addWidget(self.beats_table, 1)

        lich_su_header = QHBoxLayout()
        tieu_de = QLabel("Kịch bản đã viết")
        tieu_de.setObjectName("sectionTitle")
        lich_su_header.addWidget(tieu_de)
        lich_su_header.addStretch()
        root.addLayout(lich_su_header)

        self.history_table = DataTable(
            [Column("Thương hiệu", stretch=True),
             Column("Trạng thái", width=130),
             Column("Số đoạn", width=80),
             Column("Thao tác", width=140)],
            empty_title="Chưa viết kịch bản nào",
            empty_description="Các kịch bản đã viết sẽ hiện ở đây.")
        self.history_table.setMaximumHeight(180)
        root.addWidget(self.history_table)

    # -- Vòng đời ---------------------------------------------------------
    def on_shown(self) -> None:
        self._reload_all()

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def shutdown(self) -> None:
        for w in (self._worker, self._bp_worker, self._brand_worker):
            if w is not None and w.isRunning():
                w.wait(3000)

    # -- Nạp danh sách ----------------------------------------------------
    def _reload_all(self) -> None:
        self._bp_worker = FlowBlueprintCrudWorker("list", parent=self)
        self._bp_worker.finished_ok.connect(self._on_bp_listed)
        self._bp_worker.failed.connect(
            lambda _a, m: self.status.setText(f"Không lấy được danh sách nhịp: {m}"))
        self._bp_worker.start()

        self._brand_worker = BrandProfileWorker("list", parent=self)
        self._brand_worker.finished_ok.connect(self._on_brand_listed)
        self._brand_worker.failed.connect(
            lambda _a, m: self.status.setText(f"Không lấy được hồ sơ brand: {m}"))
        self._brand_worker.start()

        self._list_scripts()

    def _list_scripts(self) -> None:
        w = BrandScriptWorker("list", parent=self)
        w.finished_ok.connect(self._on_action_ok)
        w.failed.connect(self._on_action_failed)
        w.start()
        self._list_worker = w

    def _on_bp_listed(self, _action: str, ket) -> None:
        # Chỉ nhận Blueprint đã phân tích xong — chọn một lượt hỏng thì lát
        # nữa máy chủ mới báo lỗi, mà lúc đó người dùng đã chờ mất công.
        self._blueprints = [b for b in (ket or []) if b.get("status") == "ready"]
        self.cbo_blueprint.clear()
        for b in self._blueprints:
            nguon = str(b.get("sourceReference") or "")[:60]
            self.cbo_blueprint.addItem(f"{nguon} ({len(b.get('beats') or [])} đoạn)")
        if not self._blueprints:
            self.status.setText(
                "Chưa có nhịp kể chuyện nào — sang trang «Phân tích cấu trúc "
                "video tham khảo» chạy một lượt trước đã.")

    def _on_brand_listed(self, _action: str, ket) -> None:
        self._brands = list(ket or [])
        self.cbo_brand.clear()
        for h in self._brands:
            self.cbo_brand.addItem(str(h.get("tenBrand") or "(chưa đặt tên)"))
        if not self._brands:
            self.status.setText(
                "Chưa có hồ sơ thương hiệu nào — tạo một hồ sơ ở trang «Hồ sơ "
                "thương hiệu» trước đã.")

    # -- Viết kịch bản ----------------------------------------------------
    def _run(self) -> None:
        i_bp = self.cbo_blueprint.currentIndex()
        i_br = self.cbo_brand.currentIndex()
        if i_bp < 0 or i_bp >= len(self._blueprints):
            TOASTS.error("Chọn một nhịp kể chuyện đã.")
            return
        if i_br < 0 or i_br >= len(self._brands):
            TOASTS.error("Chọn một thương hiệu đã.")
            return

        self.btn_run.setEnabled(False)
        self.btn_use.setEnabled(False)
        self.status.setText("Đang viết kịch bản rồi đối chiếu với video nguồn…")
        self._worker = BrandScriptWorker(
            "create",
            flow_blueprint_id=str(self._blueprints[i_bp].get("id") or ""),
            brand_profile_id=str(self._brands[i_br].get("id") or ""),
            parent=self)
        self._worker.finished_ok.connect(self._on_action_ok)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _on_action_ok(self, action: str, ket) -> None:
        self.btn_run.setEnabled(True)
        if action == "list":
            self._scripts = list(ket or [])
            self._render_history()
            return
        if action == "delete":
            TOASTS.success("Đã xoá kịch bản.")
            self._list_scripts()
            return
        self._hien_tai = ket or {}
        self._render_script()
        self._list_scripts()

    def _on_action_failed(self, action: str, message: str) -> None:
        self.btn_run.setEnabled(True)
        # Hồ sơ brand thiếu trường: máy chủ CỐ Ý không tự bịa, nên đây là việc
        # người dùng phải làm chứ không phải lỗi hệ thống — nói đúng như vậy.
        if "HO_SO_BRAND_THIEU" in message or "còn thiếu" in message:
            self.status.setText(
                f"{message} — mở trang «Hồ sơ thương hiệu» bổ sung rồi quay lại.")
        else:
            self.status.setText(f"Không viết được kịch bản: {message}")
        TOASTS.error("Chưa viết được kịch bản.")

    # -- Hiển thị ---------------------------------------------------------
    def _render_script(self) -> None:
        kb = self._hien_tai or {}
        self.beats_table.clear_rows()
        for i, b in enumerate(kb.get("beats") or []):
            row = self.beats_table.add_row()
            self.beats_table.set_widget(row, 0, QLabel(_nhan_beat(b)))
            for col, khoa in ((1, "voiceoverTextVi"), (2, "captionSuggestionVi"),
                              (3, "visualBriefVi")):
                nhan = QLabel(str(b.get(khoa) or ""))
                nhan.setWordWrap(True)
                self.beats_table.set_widget(row, col, nhan)
            kiem = QLabel(_tom_tat_co(b))
            kiem.setWordWrap(True)
            self.beats_table.set_widget(row, 4, kiem)
            btn = SecondaryButton("Viết lại đoạn")
            btn.clicked.connect(lambda _c=False, idx=i: self._regenerate(idx))
            self.beats_table.set_widget(row, 5, btn)
        self.beats_table.auto_state()

        trang_thai = str(kb.get("status") or "")
        # Cửa sang H4: CHỈ `ready` mới mở. Đây là chốt cuối cùng phía giao
        # diện — máy chủ đã chặn, nhưng nút sáng lên khi chưa sạch vẫn là dạy
        # người dùng rằng cảnh báo có thể bỏ qua.
        self.btn_use.setEnabled(trang_thai == "ready")
        if trang_thai == "ready":
            self.status.setText("Kịch bản sạch — không trùng câu chữ nguồn, "
                                "không chứa cụm bị cấm.")
        elif trang_thai == "blocked":
            self.status.setText(
                "Kịch bản bị chặn: có đoạn trùng câu chữ video nguồn hoặc chứa "
                f"cụm bạn đã cấm. Viết lại những đoạn được đánh dấu {STATUS_ERROR} rồi "
                "lại — cả kịch bản phải sạch mới dùng được.")
        elif trang_thai == "unconfirmed":
            self.status.setText(
                "Chưa đối chiếu đủ với video nguồn nên chưa dám cho dùng. "
                "Xem cột «Kiểm tra» để biết vì sao từng đoạn chưa kiểm được.")
        else:
            self.status.setText(_NHAN_TRANG_THAI.get(trang_thai, trang_thai))

    def _regenerate(self, beat_index: int) -> None:
        if not self._hien_tai:
            return
        self.btn_run.setEnabled(False)
        self.btn_use.setEnabled(False)
        self.status.setText(
            f"Đang viết lại đoạn {beat_index + 1} rồi kiểm lại TOÀN BỘ kịch bản…")
        self._worker = BrandScriptWorker(
            "regenerate", script_id=str(self._hien_tai.get("id") or ""),
            beat_index=beat_index, parent=self)
        self._worker.finished_ok.connect(self._on_action_ok)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _ten_brand(self, kb: dict) -> str:
        for h in self._brands:
            if str(h.get("id")) == str(kb.get("brandProfileId")):
                return str(h.get("tenBrand") or "(chưa đặt tên)")
        return "(không rõ)"

    def _render_history(self) -> None:
        self.history_table.clear_rows()
        for kb in self._scripts:
            row = self.history_table.add_row()
            self.history_table.set_widget(row, 0, QLabel(self._ten_brand(kb)))
            tt = str(kb.get("status") or "")
            self.history_table.set_widget(
                row, 1, QLabel(_NHAN_TRANG_THAI.get(tt, tt)))
            self.history_table.set_widget(
                row, 2, QLabel(str(len(kb.get("beats") or []))))
            mo = GhostButton("Mở")
            mo.clicked.connect(lambda _c=False, k=kb: self._open(k))
            xoa = GhostButton("Xoá")
            xoa.clicked.connect(lambda _c=False, k=kb: self._delete(k))
            self.history_table.set_widgets(row, 3, [mo, xoa])
        self.history_table.auto_state()

    def _open(self, kb: dict) -> None:
        self._hien_tai = kb
        self._render_script()

    def _delete(self, kb: dict) -> None:
        confirmed, _ = ConfirmDialog.ask(
            self, "Xoá kịch bản?",
            f"Xoá kịch bản cho «{self._ten_brand(kb)}»? Không lấy lại được.",
            kind="warning", confirm_label="Xoá", cancel_label="Giữ lại")
        if not confirmed:
            return
        w = BrandScriptWorker("delete", script_id=str(kb.get("id") or ""), parent=self)
        w.finished_ok.connect(self._on_action_ok)
        w.failed.connect(self._on_action_failed)
        w.start()
        self._del_worker = w

    def _use_script(self) -> None:
        # Nút này CHỈ sáng khi trạng thái `ready` (xem `_render_script`), nên
        # tới được đây nghĩa là kịch bản đã qua cả hai lớp kiểm.
        if self._hien_tai:
            self.storyboard_requested.emit(self._hien_tai)
