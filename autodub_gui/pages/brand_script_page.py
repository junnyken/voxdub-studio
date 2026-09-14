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
from autodub_gui.ui.phase_h_ribbon import PhaseHRibbon
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
    cham = str(beat.get("chamCumNgan") or "")
    if cham:
        # Sạch, NHƯNG có chạm một cụm ngắn của nguồn. Nói ra thay vì giấu:
        # 2-3 âm tiết thường là từ vựng chủ đề ("hóa đơn" cho một brand làm
        # phần mềm hoá đơn) nên KHÔNG chặn, nhưng người viết vẫn nên biết để
        # tự quyết có đổi chữ không.
        return (f"{STATUS_OK} Không trùng câu chữ nguồn — có chạm cụm ngắn "
                f"«{cham}», không đủ để coi là chép")
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
        #: Lượt TỐN TIỀN đang chạy ("create"/"regenerate"), None nếu không có.
        #: RS-4: trước đây mọi lượt xong — kể cả `list` chạy nền — đều bật lại
        #: nút Viết, nên một lượt `list` về đích giữa lúc đang viết là mở lại
        #: đúng cái nút vừa khoá, và bấm thêm một cái là trừ tiền lần hai.
        self._dang_ton_tien: str | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)
        # H5 — dải điều hướng Phase H. Đặt ở ĐẦU vùng nội dung: đây là thứ
        # trả lời câu "tôi đang ở đâu", nên nó phải đọc được trước tiêu đề chứ
        # không nằm lẫn giữa các thẻ. Chỉ điều hướng — mọi cổng giữ nguyên.
        self.ribbon = PhaseHRibbon(1)
        root.addWidget(self.ribbon)

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
        # Lấy kịch bản RA. Trước 14/09 không có đường nào: xem được trên bảng
        # mà không sao chép, không lưu, không in ra được — mà người viết nội
        # dung thì luôn phải đưa kịch bản cho người quay, người dựng. Và khi
        # kịch bản bị CHẶN thì `Dùng kịch bản này` tắt, nên màn hình không còn
        # nút nào sáng: trông như ngõ cụt.
        self.canh_bao_nhip = QLabel("")
        self.canh_bao_nhip.setObjectName("hint")
        self.canh_bao_nhip.setWordWrap(True)
        self.canh_bao_nhip.setVisible(False)
        root.addWidget(self.canh_bao_nhip)

        self.btn_xuat = SecondaryButton("Xuất kịch bản…")
        self.btn_xuat.setEnabled(False)
        self.btn_xuat.clicked.connect(self._xuat_kich_ban)
        hanh_dong.addWidget(self.btn_xuat)
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
             # 110px không đủ cho nhãn "Viết lại đoạn" (cộng lề hai bên của
             # `set_widget`), nên chữ bị cắt thành ": lại đi" — người dùng báo
             # 14/09. Nút mà đọc không ra chữ thì coi như không có nút, đúng
             # lúc kịch bản bị chặn và đây là đường đi tiếp DUY NHẤT.
             Column("", width=160)],
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
             # Hai nút "Mở" + "Xoá" nằm chung một ô; 140px cắt cụt cả hai.
             Column("Thao tác", width=190)],
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
        self._dang_ton_tien = "create"
        self.status.setText("Đang viết kịch bản rồi đối chiếu với video nguồn…")
        self._worker = BrandScriptWorker(
            "create",
            flow_blueprint_id=str(self._blueprints[i_bp].get("id") or ""),
            brand_profile_id=str(self._brands[i_br].get("id") or ""),
            parent=self)
        self._worker.finished_ok.connect(self._on_action_ok)
        self._worker.failed.connect(self._on_action_failed)
        self._worker.start()

    def _mo_lai_nut(self, action: str) -> None:
        """Chỉ lượt TỐN TIỀN đang chạy mới được mở lại nút Viết — RS-4.

        `list` chạy nền (mở trang, sau mỗi thao tác) và `delete` đều có thể
        về đích GIỮA LÚC một lượt viết đang chạy. Mở nút theo "có lượt nào
        vừa xong" là mở nhầm lượt, và cái bấm thêm đó tốn thật 12 Vox.
        """
        if action != self._dang_ton_tien:
            return
        self._dang_ton_tien = None
        self.btn_run.setEnabled(True)

    def _on_action_ok(self, action: str, ket) -> None:
        self._mo_lai_nut(action)
        if action == "list":
            # RS-10 — KHÔNG dùng `ket or []` / `list(ket)`: danh sách rỗng là
            # falsy nên `or []` trả về một list trần và VỨT MẤT `.loi`, đúng
            # cái ca cần phân biệt. `list(...)` thì đổi kiểu, mất y như vậy.
            self._scripts = ket if isinstance(ket, list) else []
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
        self._mo_lai_nut(action)

        # RS-5 — nguồn đã bị xoá: máy chủ VỪA hạ trạng thái bản ghi này xuống,
        # nên bản sao đang giữ trong bộ nhớ đã sai kể từ giây đó. Giữ nó lại
        # là để người dùng bấm vào lịch sử, thấy `ready` cũ, rồi đi tiếp sang
        # H4 bằng một kịch bản mà chính máy chủ vừa nói là không kiểm được.
        # Bỏ bản sao cũ và hỏi lại máy chủ, chứ không tự đoán trạng thái mới.
        if "NGUON_DA_MAT" in message or "đã bị xoá" in message:
            self._hien_tai = None
            self.btn_use.setEnabled(False)
            self.beats_table.clear_rows()
            self.status.setText(
                f"{message} Danh sách vừa được tải lại từ máy chủ.")
            TOASTS.error("Nguồn của kịch bản đã bị xoá.")
            self._list_scripts()
            return

        # Mọi thất bại khác của một lượt TỐN TIỀN: phán quyết cũ chưa chắc còn
        # đúng, nên không để cổng sang H4 mở sẵn. Bấm mở lại kịch bản từ lịch
        # sử là đi qua đường đọc của máy chủ, đúng nguồn sự thật.
        if action in ("create", "regenerate"):
            self.btn_use.setEnabled(False)

        # Hồ sơ brand thiếu trường: máy chủ CỐ Ý không tự bịa, nên đây là việc
        # người dùng phải làm chứ không phải lỗi hệ thống — nói đúng như vậy.
        if "HO_SO_BRAND_THIEU" in message or "còn thiếu" in message:
            self.status.setText(
                f"{message} — mở trang «Hồ sơ thương hiệu» bổ sung rồi quay lại.")
        elif "BLUEPRINT_KHONG_KIEM_DUOC" in message:
            # RS-3: máy chủ chặn TRƯỚC khi trừ tiền — nói rõ là chưa mất Vox,
            # không thì người dùng tưởng vừa trả tiền cho một lỗi.
            self.status.setText(f"{message}")
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

        self._canh_bao_nhip()
        trang_thai = str(kb.get("status") or "")
        # Cửa sang H4: CHỈ `ready` mới mở. Đây là chốt cuối cùng phía giao
        # diện — máy chủ đã chặn, nhưng nút sáng lên khi chưa sạch vẫn là dạy
        # người dùng rằng cảnh báo có thể bỏ qua.
        self.btn_use.setEnabled(trang_thai == "ready")
        # Xuất được kể cả khi BỊ CHẶN: kịch bản chặn vẫn là thứ người dùng vừa
        # trả 12 Vox để có, và họ cần đọc/sửa nó ở ngoài. Chỉ cổng sang H4 mới
        # đòi sạch.
        self.btn_xuat.setEnabled(bool(kb.get("beats")))
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
        self._dang_ton_tien = "regenerate"
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
        # RS-10 — "chưa có kịch bản nào" và "không hỏi được máy chủ" là hai
        # câu khác nhau; trước đây cả hai ra cùng một màn hình.
        self.history_table.auto_state(getattr(self._scripts, "loi", ""))

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

    def _canh_bao_nhip(self) -> None:
        """Kịch bản đọc hết bao lâu so với video nguồn — H6.

        Bộ dò này vốn nằm ở H4 (`storyboard.dung_storyboard`), tức người dùng
        chỉ biết SAU KHI đã tiêu 12 Vox viết kịch bản và đi thêm một trang.
        Pilot 14/09 lộ ra đúng chỗ đó: nguồn 34 giây, kịch bản 170 giây, và
        chủ dự án chỉ thấy dòng cảnh báo ở màn hình cuối.

        Dùng LẠI `uoc_luong_giay_doc` của `autodub.storyboard` — không tự tính
        lại, vì hai hằng số tốc độ đọc ở đó đã đo thật trên bốn giọng.
        """
        # XOÁ chữ, không chỉ ẩn: một nhãn ẩn mà còn chữ cũ sẽ hiện lại nguyên
        # cảnh báo của kịch bản TRƯỚC ngay khi có thứ khác bật nó lên.
        self.canh_bao_nhip.setText("")
        self.canh_bao_nhip.setVisible(False)
        kb = self._hien_tai or {}
        beats = kb.get("beats") or []
        if not beats:
            return
        bp = next((b for b in self._blueprints
                   if str(b.get("id")) == str(kb.get("flowBlueprintId"))), None)
        cuoi = [float(b.get("endS") or 0) for b in ((bp or {}).get("beats") or [])]
        nguon_giay = max(cuoi) if cuoi else 0.0
        if nguon_giay <= 0:
            return

        from autodub.storyboard import uoc_luong_giay_doc

        tong = sum(uoc_luong_giay_doc(str(b.get("voiceoverTextVi") or "")).giay
                   for b in beats)
        if tong <= 0:
            return
        ti_le = tong / nguon_giay
        if ti_le < 1.5 and ti_le > 1 / 1.5:
            return
        huong = "dài gấp" if ti_le >= 1.5 else "ngắn hơn"
        self.canh_bao_nhip.setText(
            f"{STATUS_WARN} Kịch bản đọc hết khoảng {tong:.0f} giây, {huong} "
            f"{ti_le:.1f} lần video tham khảo ({nguon_giay:.0f} giây) — nhịp "
            "kể chuyện học được sẽ không còn giống nữa. Bấm «Viết lại đoạn» ở "
            "những đoạn dài nhất, hoặc chọn một video tham khảo dài tương đương.")
        self.canh_bao_nhip.setVisible(True)

    def _xuat_kich_ban(self) -> None:
        """Ghi kịch bản ra tệp chữ đọc được, kèm phần KIỂM của từng đoạn.

        Xuất cả cột kiểm tra chứ không chỉ lời đọc: người cầm kịch bản đi quay
        cần biết đoạn nào đang bị chặn và vì sao, nếu không họ quay cả đoạn sẽ
        phải bỏ.
        """
        from PySide6.QtWidgets import QFileDialog

        kb = self._hien_tai or {}
        beats = kb.get("beats") or []
        if not beats:
            return
        ten_goi_y = f"kich-ban-{self._ten_brand(kb)}.txt".replace(" ", "-")
        duong_dan, _ = QFileDialog.getSaveFileName(
            self, "Lưu kịch bản", ten_goi_y, "Tệp chữ (*.txt)")
        if not duong_dan:
            return

        dong = [
            f"KỊCH BẢN — {self._ten_brand(kb)}",
            f"Trạng thái: {_NHAN_TRANG_THAI.get(str(kb.get('status') or ''), kb.get('status'))}",
            "",
        ]
        for i, b in enumerate(beats, 1):
            dong += [
                f"--- Đoạn {i}: {_nhan_beat(b)} ---",
                f"Lời đọc     : {b.get('voiceoverTextVi') or ''}",
                f"Chữ trên hình: {b.get('captionSuggestionVi') or ''}",
                f"Cần quay gì  : {b.get('visualBriefVi') or ''}",
                f"Kiểm tra     : {_tom_tat_co(b)}",
                "",
            ]
        # Dựng chuỗi XONG rồi mới mở tệp: `open(p, "w")` cắt trắng tệp cũ ngay
        # cả khi phần dựng ném lỗi sau đó.
        tho = "\n".join(dong)
        try:
            with open(duong_dan, "w", encoding="utf-8") as f:
                f.write(tho)
        except OSError as e:
            TOASTS.error(f"Không lưu được: {e}")
            return
        TOASTS.success(f"Đã lưu kịch bản: {duong_dan}")

    def _use_script(self) -> None:
        # Nút này CHỈ sáng khi trạng thái `ready` (xem `_render_script`), nên
        # tới được đây nghĩa là kịch bản đã qua cả hai lớp kiểm.
        if self._hien_tai:
            self.storyboard_requested.emit(self._hien_tai)
