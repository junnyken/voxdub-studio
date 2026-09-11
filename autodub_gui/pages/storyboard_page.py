"""Trang Dựng video từ kịch bản — mini-spec H4e.

Nhận một kịch bản brand ĐÃ `ready` (H3), hiện dòng thời gian từng đoạn, cho
gán ảnh cho mỗi đoạn, rồi dựng thư mục dự án mở thẳng trong Trình chỉnh sửa.

**Không tốn Vox.** Ghép ảnh và tính thời lượng chạy hết trên máy; giọng đọc do
Trình chỉnh sửa lo bằng VieNeu cũng chạy trên máy. Trang này KHÔNG có đường
sinh ảnh tự động — thiếu ảnh thì người dùng tự chọn hoặc chủ động nhờ vẽ, vì
mỗi tấm tốn 33 Vox (30 vẽ + 3 kiểm) và tự bấm hộ là tiêu tiền của người ta
mà không xin phép.

**Thời gian hiện ra là KHOẢNG, không phải một con số.** Bốn giọng dựng sẵn đọc
chênh nhau 1,21 lần (đo thật) — hiện "8,4 giây" thì người dùng dựng hình khít
theo đó rồi lệch tiếng; hiện "khoảng 7–10 giây" thì họ biết mà chừa biên.
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.pages import BasePage
from autodub_gui.status_text import STATUS_ERROR, STATUS_OK, STATUS_WARN
from autodub_gui.ui.buttons import GhostButton, PrimaryButton, SecondaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.table import Column, DataTable
from autodub_gui.ui.toast import TOASTS
from autodub_gui.workers import (
    DungDuAnWorker, FlowBlueprintCrudWorker, SinhAnhMinhHoaWorker,
)

_PAGE_MARGIN = 28
_ANH_FILTER = "Ảnh (*.png *.jpg *.jpeg *.webp);;Tất cả (*.*)"

#: Giá THẬT của một ảnh minh hoạ: 30 Vox vẽ (`credit.cost.image.scene`) cộng
#: 3 Vox kiểm (`credit.cost.assist.kiem_anh_minh_hoa`) — mỗi ảnh là HAI lượt
#: tính tiền, không phải một.
#:
#: Bản đầu của trang này chỉ ghi 30 và bỏ quên lượt kiểm, nên hộp thoại nói
#: "5 ảnh — hết 150 Vox" trong khi ví bị trừ 165. Hiện sai giá ở chỗ xin phép
#: thì lượt bấm không còn là đồng ý — và người dùng chỉ phát hiện sau khi mất
#: tiền.
GIA_VE = 30
GIA_KIEM = 3
GIA_MOI_ANH = GIA_VE + GIA_KIEM

_NHAN_BEAT = {
    "hook": "Mở hook", "problem_context": "Nêu vấn đề", "tension": "Tăng kịch tính",
    "proof": "Bằng chứng", "demonstration": "Trình diễn",
    "payoff": "Cao trào / kết quả", "twist": "Bất ngờ",
    "objection": "Giải đáp phản bác", "cta": "Kêu gọi hành động",
    "transition": "Chuyển đoạn", "unknown": "Chưa xác định",
}


def _khoang_giay(uoc) -> str:
    """Hiện KHOẢNG thời gian, không phải một con số giả vờ chính xác."""
    return f"khoảng {uoc.giay_min:.0f}–{uoc.giay_max:.0f} giây"


class StoryboardPage(BasePage):
    """Dựng video từ một kịch bản brand đã duyệt."""

    #: Dự án dựng xong -> mở thẳng Trình chỉnh sửa (app.py nối signal này).
    open_editor_requested = Signal(str)

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._kich_ban: dict | None = None
        self._blueprint: dict | None = None
        self._board = None
        self._anh: list[str] = []
        self._worker: DungDuAnWorker | None = None
        self._bp_worker: FlowBlueprintCrudWorker | None = None
        self._ve_worker: SinhAnhMinhHoaWorker | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        card = Card(padding=tokens.SP_4)
        card.add_header("Dựng video từ kịch bản")
        hint = QLabel(
            "Mỗi đoạn giữ hình đúng bằng thời gian đọc lời của nó. Chọn ảnh "
            "cho từng đoạn rồi bấm «Dựng dự án» — ghép và dựng không tốn Vox. "
            "Xong sẽ mở trong Trình chỉnh sửa để bạn nghe thử, sửa lời và "
            f"xuất video. Thiếu ảnh thì có thể nhờ vẽ, {GIA_MOI_ANH} Vox mỗi "
            "tấm — công cụ luôn hỏi trước khi trừ.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        card.body.addWidget(hint)
        root.addWidget(card)

        self.status = QLabel("Chưa chọn kịch bản nào.")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.canh_bao = QLabel("")
        self.canh_bao.setObjectName("hint")
        self.canh_bao.setWordWrap(True)
        self.canh_bao.hide()
        root.addWidget(self.canh_bao)

        self.bang = DataTable(
            [Column("Đoạn", width=140),
             Column("Lời đọc", stretch=True),
             Column("Thời lượng", width=150),
             Column("Ảnh", stretch=True),
             Column("", width=120)],
            empty_title="Chưa có kịch bản",
            empty_description="Mở một kịch bản đã duyệt từ trang «Viết kịch bản».")
        root.addWidget(self.bang, 1)

        hang = QHBoxLayout()
        hang.setSpacing(tokens.SP_3)
        self.btn_dung = PrimaryButton("Dựng dự án")
        self.btn_dung.setEnabled(False)
        self.btn_dung.clicked.connect(self._dung)
        hang.addWidget(self.btn_dung)
        self.btn_chon_het = GhostButton("Chọn ảnh cho tất cả…")
        self.btn_chon_het.clicked.connect(self._chon_nhieu)
        hang.addWidget(self.btn_chon_het)
        self.btn_ve_het = GhostButton("Vẽ ảnh cho các đoạn còn thiếu…")
        self.btn_ve_het.clicked.connect(lambda: self._ve_anh(self._doan_thieu()))
        hang.addWidget(self.btn_ve_het)
        hang.addStretch()
        root.addLayout(hang)

    # -- Nhận kịch bản từ trang «Viết kịch bản» ----------------------------
    def dat_kich_ban(self, kich_ban: dict) -> None:
        """Trang «Viết kịch bản» gọi hàm này khi người dùng bấm dùng kịch bản."""
        self._kich_ban = kich_ban or {}
        self._blueprint = None
        self._anh = [""] * len(self._kich_ban.get("beats") or [])
        self._tai_blueprint()
        self._ve()

    def _tai_blueprint(self) -> None:
        """Lấy Flow Blueprint gốc để so nhịp — cả điểm của H2 là học nhịp,
        nên kịch bản dài gấp rưỡi nguồn là chuyện đáng nói."""
        bp_id = str((self._kich_ban or {}).get("flowBlueprintId") or "")
        if not bp_id:
            return
        w = FlowBlueprintCrudWorker("list", parent=self)
        w.finished_ok.connect(lambda _a, ds: self._nhan_blueprint(bp_id, ds))
        # Thiếu blueprint chỉ mất phần so nhịp, không chặn dựng video.
        w.failed.connect(lambda _a, _m: None)
        w.start()
        self._bp_worker = w

    def _nhan_blueprint(self, bp_id: str, ds) -> None:
        for b in ds or []:
            if str(b.get("id")) == bp_id:
                self._blueprint = b
                break
        self._ve()

    # -- Vẽ ---------------------------------------------------------------
    def _ve(self) -> None:
        from autodub.storyboard import KichBanChuaDungDuoc, dung_storyboard

        self.bang.clear_rows()
        if not self._kich_ban:
            self.bang.auto_state()
            return
        try:
            self._board = dung_storyboard(self._kich_ban, self._blueprint)
        except KichBanChuaDungDuoc as e:
            # Cổng của H4 nằm ở tầng hàm; giao diện chỉ nói lại cho dễ hiểu.
            self._board = None
            self.status.setText(f"{STATUS_ERROR} {e}")
            self.btn_dung.setEnabled(False)
            # Kịch bản chưa duyệt thì cũng KHÔNG được vẽ ảnh cho nó. Cổng của
            # H4 là "chỉ kịch bản ready" — để hở đường tiêu tiền ở đây thì
            # người dùng trả 33 Vox mỗi ảnh cho một kịch bản không dựng được.
            self.btn_ve_het.setEnabled(False)
            self.bang.auto_state()
            return

        for i, d in enumerate(self._board.doan):
            row = self.bang.add_row()
            self.bang.set_widget(row, 0, QLabel(_NHAN_BEAT.get(d.beat_type, d.beat_type)))
            loi = QLabel(d.loi_doc)
            loi.setWordWrap(True)
            self.bang.set_widget(row, 1, loi)
            self.bang.set_widget(row, 2, QLabel(_khoang_giay(d.uoc_luong)))
            duong = self._anh[i] if i < len(self._anh) else ""
            if duong:
                nhan = QLabel(os.path.basename(duong))
            else:
                # Hiện GỢI Ý HÌNH ngay ở đây, không giấu trong hộp thoại: đây
                # là thứ người dùng cần đọc để quyết có bỏ 30 Vox vẽ hay tự đi
                # chụp một tấm.
                nhan = QLabel(f"{STATUS_WARN} chưa có ảnh"
                              + (f" — gợi ý: {d.visual_brief}"
                                 if d.visual_brief else ""))
            nhan.setWordWrap(True)
            self.bang.set_widget(row, 3, nhan)
            o = QWidget()
            cot = QHBoxLayout(o)
            cot.setContentsMargins(0, 0, 0, 0)
            cot.setSpacing(tokens.SP_2)
            nut = SecondaryButton("Đổi ảnh…" if duong else "Chọn ảnh…")
            nut.clicked.connect(lambda _c=False, idx=i: self._chon_mot(idx))
            cot.addWidget(nut)
            if not duong:
                ve = GhostButton(f"Vẽ ({GIA_MOI_ANH} Vox)")
                ve.clicked.connect(lambda _c=False, idx=i: self._ve_anh([idx]))
                cot.addWidget(ve)
            self.bang.set_widget(row, 4, o)
        self.bang.auto_state()

        du_anh = all(str(a or "").strip() for a in self._anh) and bool(self._anh)
        self.btn_dung.setEnabled(du_anh)
        thieu = sum(1 for a in self._anh if not str(a or "").strip())
        # Chỉ bật nút vẽ khi thật sự có đoạn thiếu ảnh VÀ có gợi ý để vẽ theo.
        # Bật nút rồi mới báo "không có gợi ý" là dạy người dùng bấm bừa.
        self.btn_ve_het.setEnabled(any(
            str(self._board.doan[i].visual_brief or "").strip()
            for i in self._doan_thieu() if i < len(self._board.doan)))
        if du_anh:
            self.status.setText(
                f"{STATUS_OK} Đủ ảnh cho {len(self._anh)} đoạn. Video sẽ dài "
                f"khoảng {self._board.tong_giay_min:.0f}–"
                f"{self._board.tong_giay_max:.0f} giây.")
        else:
            self.status.setText(
                f"{STATUS_WARN} Còn {thieu} đoạn chưa có ảnh. Chọn đủ rồi mới "
                "dựng được — công cụ không tự sinh ảnh thay bạn.")

        if self._board.canh_bao:
            self.canh_bao.setText(f"{STATUS_WARN} "
                                  + "  ".join(self._board.canh_bao))
            self.canh_bao.show()
        else:
            self.canh_bao.hide()

    # -- Chọn ảnh ---------------------------------------------------------
    def _chon_mot(self, i: int) -> None:
        duong, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh cho đoạn này",
                                               "", _ANH_FILTER)
        if duong:
            self._anh[i] = duong
            self._ve()

    def _chon_nhieu(self) -> None:
        if not self._board:
            return
        ds, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh theo đúng thứ tự đoạn", "", _ANH_FILTER)
        if not ds:
            return
        for i, duong in enumerate(ds[:len(self._anh)]):
            self._anh[i] = duong
        if len(ds) < len(self._anh):
            TOASTS.info(f"Đã gán {len(ds)} ảnh, còn "
                        f"{len(self._anh) - len(ds)} đoạn chưa có.")
        self._ve()

    # -- Vẽ ảnh (mini-spec H4d) -------------------------------------------
    def _doan_thieu(self) -> list[int]:
        return [i for i, a in enumerate(self._anh) if not str(a or "").strip()]

    def _ve_anh(self, chi_so: list[int]) -> None:
        """Hỏi kèm GIÁ rồi mới vẽ. Không có đường nào vẽ mà không qua đây.

        Guardrail 3 của H4d. Tự bấm hộ là tiêu tiền của người ta mà không xin
        phép, nên hộp thoại này không phải thủ tục — nó là chỗ người dùng nhìn
        thấy con số trước khi con số bị trừ.
        """
        if not self._board or not chi_so:
            return
        # Lượt vẽ trước chưa xong mà bấm tiếp thì worker cũ bị ghi đè, còn
        # tiền của nó thì đã trừ rồi — người dùng mất Vox cho những tấm ảnh
        # không bao giờ tới nơi. Nút hàng loạt đã tắt, nhưng nút vẽ từng dòng
        # thì không, nên chốt phải nằm ở đây.
        if self._ve_worker is not None and self._ve_worker.isRunning():
            TOASTS.info("Đang vẽ dở — đợi xong rồi hãy vẽ tiếp.")
            return
        goi_y = [(i, self._board.doan[i].visual_brief) for i in chi_so
                 if i < len(self._board.doan)]
        goi_y = [(i, g) for i, g in goi_y if str(g or "").strip()]
        if not goi_y:
            TOASTS.info("Kịch bản không có gợi ý hình cho đoạn này — "
                        "chọn ảnh của bạn nhé.")
            return

        tong = len(goi_y) * GIA_MOI_ANH
        dong_y, _ = ConfirmDialog.ask(
            self, f"Vẽ {len(goi_y)} ảnh — hết {tong} Vox",
            f"Mỗi ảnh tốn {GIA_MOI_ANH} Vox, tổng {tong} Vox cho "
            f"{len(goi_y)} đoạn. Tiền trừ ngay cả khi ảnh vẽ ra không dùng "
            "được, nên đọc gợi ý bên dưới rồi hãy quyết.",
            kind="warning", confirm_label=f"Vẽ, trừ {tong} Vox",
            cancel_label="Thôi",
            # Cho họ ĐỌC ĐÚNG thứ sắp được vẽ. Hỏi trả tiền cho một tấm ảnh
            # sinh từ gợi ý không hiện ở đâu cả thì lượt bấm không còn là
            # đồng ý có hiểu biết.
            detail="Sẽ vẽ theo những gợi ý này:\n"
                   + "\n".join(f"  {i + 1}. {g}" for i, g in goi_y)
                   + "\n\nẢnh vẽ ra là ảnh MINH HOẠ, không phải ảnh sản phẩm "
                     "của bạn — công cụ cố ý không vẽ hộp, chai hay nhãn nào, "
                     "vì sản phẩm bịa trong video bán hàng là thứ khiến tài "
                     "khoản bị phạt.\n\n"
                     "Nếu ảnh có người thì mỗi đoạn sẽ là một người KHÁC "
                     "nhau. Công cụ không giữ được cùng một nhân vật giữa các "
                     "cảnh.\n\n"
                     "Ảnh nào vẽ ra mà có sản phẩm hoặc chữ đọc được sẽ bị "
                     "loại, không ghép vào video.")
        if not dong_y:
            return

        thu_muc = os.path.join(os.path.expanduser("~"), "VoxDub", "storyboard",
                               "anh_minh_hoa",
                               time.strftime("%Y%m%d_%H%M%S"))
        self.btn_ve_het.setEnabled(False)
        self.status.setText(f"Đang vẽ {len(goi_y)} ảnh…")
        self._ve_worker = SinhAnhMinhHoaWorker(goi_y, thu_muc, parent=self)
        self._ve_worker.tien_do.connect(
            lambda i, tong_: self.status.setText(f"Đang vẽ ảnh {i + 1}/{tong_}…"))
        self._ve_worker.finished_ok.connect(self._ve_anh_xong)
        self._ve_worker.failed.connect(self._ve_anh_hong)
        self._ve_worker.start()

    def _ve_anh_xong(self, me) -> None:
        """Chỉ ảnh ĐẠT mới vào video. Ảnh trượt vẫn nói ra, kèm lý do."""
        self.btn_ve_het.setEnabled(True)
        dat = 0
        for ket in me.ket_qua:
            # Đi theo `chi_so` của chính kết quả, KHÔNG theo thứ tự trong
            # danh sách: vẽ riêng cho một đoạn, hoặc một đoạn hỏng giữa mẻ,
            # đều làm hai thứ đó lệch nhau — và ảnh sẽ lên nhầm đoạn.
            if ket.dung_duoc and 0 <= ket.chi_so < len(self._anh):
                self._anh[ket.chi_so] = ket.duong_dan
                dat += 1
        self._ve()

        truot = [k for k in me.ket_qua if not k.dung_duoc]
        if truot:
            # Người dùng đã trả tiền cho những tấm này — họ có quyền biết vì
            # sao chúng không dùng được, không phải chỉ thấy một con số hụt.
            ConfirmDialog.show_error(
                self, f"{len(truot)} ảnh không dùng được",
                f"Đã vẽ {len(me.ket_qua)} ảnh, {dat} ảnh dùng được. "
                f"{len(truot)} ảnh bị loại vì không qua được bước kiểm — "
                "Vox của những ảnh đó vẫn bị trừ vì máy chủ đã vẽ chúng.",
                detail="\n".join(f"• {k.goi_y[:60]} → {k.ly_do}" for k in truot))
        elif dat:
            TOASTS.success(f"Đã vẽ xong {dat} ảnh.")

    def _ve_anh_hong(self, message: str) -> None:
        self.btn_ve_het.setEnabled(True)
        self._ve()
        ConfirmDialog.show_error(self, "Không vẽ được ảnh", message)

    # -- Dựng -------------------------------------------------------------
    def _dung(self) -> None:
        if not self._kich_ban or not self._board:
            return
        goc = os.path.join(os.path.expanduser("~"), "VoxDub", "storyboard")
        work_dir = os.path.join(goc, time.strftime("%Y%m%d_%H%M%S") + "_vi")

        self.btn_dung.setEnabled(False)
        self.status.setText("Đang ghép ảnh thành video… (không tốn Vox)")
        self._worker = DungDuAnWorker(self._kich_ban, self._anh, work_dir,
                                      blueprint=self._blueprint, parent=self)
        self._worker.finished_ok.connect(self._xong)
        self._worker.failed.connect(self._hong)
        self._worker.start()

    def _xong(self, ket) -> None:
        self.btn_dung.setEnabled(True)
        self.status.setText(f"{STATUS_OK} Đã dựng dự án. Đang mở Trình chỉnh sửa…")
        TOASTS.success("Dựng xong — nghe thử và sửa lời trong Trình chỉnh sửa.")
        self.open_editor_requested.emit(ket.work_dir)

    def _hong(self, message: str) -> None:
        self.btn_dung.setEnabled(True)
        self.status.setText(f"{STATUS_ERROR} Không dựng được dự án: {message}")
        TOASTS.error("Không dựng được dự án.")

    # -- Vòng đời ---------------------------------------------------------
    def is_running(self) -> bool:
        return any(w is not None and w.isRunning()
                   for w in (self._worker, self._ve_worker))

    def shutdown(self) -> None:
        for w in (self._worker, self._bp_worker, self._ve_worker):
            if w is not None and w.isRunning():
                w.wait(3000)
