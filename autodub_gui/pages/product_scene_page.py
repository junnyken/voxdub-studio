"""Trang Ảnh sản phẩm — dựng bối cảnh cho ảnh chụp, có cổng tuân thủ (C1).

Người bán TikTok Shop có một ảnh chụp sản phẩm bằng điện thoại và cần vài
ảnh nền đẹp để dựng video. Việc đó AI làm được trong mười giây. Cái bẫy nằm
ở chỗ khác: TikTok Shop **tự động** đối chiếu hình trong video với sản phẩm
đang bán, và lệch là mất quyền bán — một tài khoản thật đã bị hủy quyền
thương mại điện tử kèm trừ 1000 điểm vì đúng lỗi "quảng bá sản phẩm không
nhất quán".

Nên trang này cố tình KHÔNG chỉ là nút "tạo ảnh đẹp". Ba điều nó ép:

* Mặc định là **Giữ nguyên sản phẩm** — chỉ đổi bối cảnh quanh sản phẩm.
* Ảnh nào cũng đi qua bước kiểm, và **kết quả kiểm đè lên chế độ người dùng
  chọn**: xin giữ nguyên mà máy dựng lệch nhãn thì ảnh đó vẫn bị đánh dấu
  không dùng để bán được.
* Ảnh "Ý tưởng" (được vẽ lại bao bì) luôn đóng nhãn cảnh báo và không bao
  giờ hiện ra như ảnh dùng để đăng bán.

Người dùng vẫn có quyền tải mọi ảnh về. Thứ trang này không cho phép là
**nhầm lẫn** giữa hai loại.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QScrollArea, QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.pages import BasePage
from autodub_gui.system_open import open_folder
from autodub_gui.ui.badges import StatusBadge
from autodub_gui.ui.buttons import GhostButton, PrimaryButton, SecondaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.style import clear_background
from autodub_gui.ui.inputs import LabeledCombo, LabeledLineEdit
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import (
    ProductSceneWorker, ProductVideoWorker, SceneScriptWorker,
)

_PAGE_MARGIN = 28
_ANH_W = 190          # bề rộng ảnh xem trước trong lưới kết quả
_COT = 3              # số ảnh mỗi hàng

#: Phải khớp `BOI_CANH` trong `control_server/src/prompts/product_scene.js`.
#: Có test đối chiếu hai danh sách; đổi một bên mà quên bên kia thì test đỏ.
BOI_CANH: list[tuple[str, str]] = [
    ("ban_go", "Bàn gỗ mộc"),
    ("bep_gia_dinh", "Bếp gia đình"),
    ("nen_studio", "Nền studio"),
    ("gio_qua", "Giỏ quà"),
    ("ngoai_troi", "Ngoài trời"),
    ("tay_cam", "Trên tay"),
]

#: Nhãn CHỌN chế độ. Chữ nói thẳng hậu quả, không nói tên kỹ thuật —
#: "SAFE/CONCEPT" không giúp người bán quyết định được gì.
_CHE_DO = [
    ("Giữ nguyên sản phẩm — đăng bán được", "SAFE"),
    ("Ý tưởng bao bì mới — KHÔNG đăng kèm hàng đang bán", "CONCEPT"),
]

#: Mỗi ảnh tốn Vox, và mỗi lượt đều gọi thêm một lượt kiểm. Chặn ở đây để
#: không ai lỡ tay chọn cả sáu rồi mới nhìn hoá đơn.
_TOI_DA_MOI_LUOT = 4

_ANH_FILTER = "Ảnh (*.jpg *.jpeg *.png *.webp);;Tất cả (*.*)"


class ProductScenePage(BasePage):
    """Dựng nhiều bối cảnh từ một ảnh sản phẩm, kèm phán quyết tuân thủ."""

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: ProductSceneWorker | None = None
        self._worker_video: ProductVideoWorker | None = None
        self._worker_kich_ban: SceneScriptWorker | None = None
        self._anh_kich_ban: list = []
        self._thu_muc_ket_qua = ""
        self._o_boi_canh: dict[str, QCheckBox] = {}
        self._build()

    # ------------------------------------------------------------ dựng UI --
    def _build(self) -> None:
        # Trang này PHẢI cuộn được. Không cuộn thì khi cửa sổ thấp hơn nội
        # dung, Qt ép mọi ô nhập xuống dưới chiều cao tối thiểu của chúng —
        # chữ trong ô bị cắt ngang, các hàng trông như chồng lên nhau. Chủ dự
        # án gặp đúng cảnh đó ở v3.6.1, sau khi C10 thêm thẻ "Thứ tự cảnh"
        # làm nội dung dài thêm một đoạn.
        #
        # Cùng khuôn với trang Cài đặt: viewport tự co giãn, không viền, không
        # thanh cuộn ngang (cuộn ngang là dấu hiệu bố cục sai, không phải tính
        # năng).
        ngoai = QVBoxLayout(self)
        ngoai.setContentsMargins(0, 0, 0, 0)
        vung_cuon = QScrollArea()
        vung_cuon.setWidgetResizable(True)
        vung_cuon.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vung_cuon.setFrameShape(QScrollArea.Shape.NoFrame)
        khung = QWidget()
        clear_background(khung)
        ngoai.addWidget(vung_cuon)

        root = QVBoxLayout(khung)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN,
                                tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        card = Card(padding=tokens.SP_4)
        card.add_header("Ảnh sản phẩm")

        self.anh_goc = LabeledLineEdit(
            "Ảnh sản phẩm của bạn", "D:\\anh\\san-pham.jpg",
            "Chụp bằng điện thoại cũng được, miễn nhìn rõ nhãn và bao bì.")
        card.body.addWidget(self.anh_goc)

        hang_chon = QHBoxLayout()
        hang_chon.setSpacing(tokens.SP_2)
        self.btn_pick = SecondaryButton("Chọn ảnh…")
        self.btn_pick.clicked.connect(self._chon_anh)
        hang_chon.addWidget(self.btn_pick)
        hang_chon.addStretch()
        card.body.addLayout(hang_chon)

        nhan_bc = QLabel(f"Bối cảnh muốn dựng (tối đa {_TOI_DA_MOI_LUOT} mỗi lượt)")
        nhan_bc.setObjectName("hint")
        card.body.addWidget(nhan_bc)

        luoi = QGridLayout()
        luoi.setSpacing(tokens.SP_2)
        for i, (khoa, ten) in enumerate(BOI_CANH):
            o = QCheckBox(ten)
            self._o_boi_canh[khoa] = o
            luoi.addWidget(o, i // _COT, i % _COT)
        self._o_boi_canh[BOI_CANH[0][0]].setChecked(True)
        card.body.addLayout(luoi)

        self.che_do = LabeledCombo(
            "Chế độ", _CHE_DO,
            "Giữ nguyên sản phẩm là chế độ duy nhất an toàn để đăng bán. "
            "Chế độ ý tưởng dựng lại cả bao bì — đẹp để tham khảo, nhưng "
            "dùng làm ảnh bán hàng là đúng lỗi TikTok Shop đang phạt.")
        card.body.addWidget(self.che_do)

        self.ghi_chu = LabeledLineEdit(
            "Ghi chú thêm (không bắt buộc)", "ví dụ: đặt cạnh ly cà phê",
            "Mô tả bối cảnh bạn muốn. Không dùng để đổi sản phẩm.")
        card.body.addWidget(self.ghi_chu)

        self.thu_muc = LabeledLineEdit(
            "Thư mục lưu ảnh", "",
            "Để trống thì lưu vào thư mục «anh_san_pham» cạnh các dự án.")
        card.body.addWidget(self.thu_muc)
        root.addWidget(card)

        hanh_dong = QHBoxLayout()
        hanh_dong.setSpacing(tokens.SP_3)
        self.btn_run = PrimaryButton("Dựng ảnh")
        self.btn_run.clicked.connect(self._chay)
        hanh_dong.addWidget(self.btn_run)
        self.btn_video = GhostButton("Dựng video ngắn")
        self.btn_video.setToolTip(
            "Ghép các ảnh ĐÃ ĐƯỢC DUYỆT thành một video dọc. Ảnh lệch bao bì "
            "hoặc chưa kiểm được sẽ không được đưa vào.")
        self.btn_video.clicked.connect(self._dung_video)
        hanh_dong.addWidget(self.btn_video)
        self.btn_kich_ban = GhostButton("Gợi ý kịch bản")
        self.btn_kich_ban.setToolTip(
            "Nhờ trợ lý gợi ý câu dẫn và nhịp cho từng cảnh. Chỉ là gợi ý — "
            "không có gì được tự dán vào video.")
        self.btn_kich_ban.clicked.connect(self._goi_y_kich_ban)
        hanh_dong.addWidget(self.btn_kich_ban)
        self.btn_open = GhostButton("Mở thư mục ảnh")
        self.btn_open.clicked.connect(self._mo_thu_muc)
        self.btn_open.setEnabled(False)
        hanh_dong.addWidget(self.btn_open)
        hanh_dong.addStretch()
        root.addLayout(hanh_dong)

        # Thứ tự cảnh: danh sách này CHỈ chứa ảnh đăng bán được. Ảnh lệch
        # nhãn và ảnh chưa kiểm được không có mặt ở đây — không phải để giấu,
        # mà vì đây là danh sách "đưa vào video", và chúng không được vào.
        # Lý do vì sao chúng không được vào vẫn hiện dưới từng ảnh ở lưới
        # kết quả.
        the_thu_tu = Card(padding=tokens.SP_4)
        the_thu_tu.add_header("Thứ tự cảnh trong video")
        goi_y = QLabel("Kéo để đổi thứ tự. Bỏ tích ảnh không muốn đưa vào.")
        goi_y.setObjectName("hint")
        the_thu_tu.body.addWidget(goi_y)

        self.thu_tu = QListWidget()
        self.thu_tu.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.thu_tu.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.thu_tu.setMinimumHeight(150)
        self.thu_tu.setMaximumHeight(240)
        the_thu_tu.body.addWidget(self.thu_tu)
        root.addWidget(the_thu_tu)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        # Khung Nhật ký: chỗ duy nhất đủ dài để in gợi ý kịch bản từng cảnh
        # và câu cảnh báo liên tục — dòng trạng thái một dòng không chứa nổi.
        self.log = LogPanel()
        self.log.setMaximumHeight(150)
        root.addWidget(self.log)

        self.ket_qua = QGridLayout()
        self.ket_qua.setSpacing(tokens.SP_3)
        root.addLayout(self.ket_qua)
        root.addStretch()

        vung_cuon.setWidget(khung)

    # ----------------------------------------------------------- hành động --
    def _chon_anh(self) -> None:
        duong, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh sản phẩm", "", _ANH_FILTER)
        if duong:
            self.anh_goc.set_text(duong)

    def _boi_canh_da_chon(self) -> list[str]:
        return [k for k, o in self._o_boi_canh.items() if o.isChecked()]

    def _thu_muc_ra(self) -> str:
        chon = self.thu_muc.text().strip()
        if chon:
            return chon
        settings = self._settings_provider()
        return os.path.join(str(getattr(settings, "output_dir", "") or "."),
                            "anh_san_pham")

    def _chay(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            TOASTS.warn("Đang dựng ảnh — chờ lượt này xong đã.")
            return

        anh = self.anh_goc.text().strip()
        if not anh:
            TOASTS.warn("Chọn ảnh sản phẩm trước đã.")
            return
        if not os.path.isfile(anh):
            TOASTS.warn(f"Không tìm thấy ảnh: {anh}")
            return

        chon = self._boi_canh_da_chon()
        if not chon:
            TOASTS.warn("Chọn ít nhất một bối cảnh.")
            return
        if len(chon) > _TOI_DA_MOI_LUOT:
            TOASTS.warn(f"Mỗi lượt dựng tối đa {_TOI_DA_MOI_LUOT} bối cảnh — "
                        "bỏ bớt rồi chạy lại lượt sau.")
            return

        self._xoa_ket_qua()
        thu_muc = self._thu_muc_ra()
        self._thu_muc_ket_qua = thu_muc
        self.btn_run.setEnabled(False)
        self.status.setText("Đang dựng…")

        worker = ProductSceneWorker(
            anh, chon, thu_muc,
            che_do=str(self.che_do.current_key() or "SAFE"),
            ghi_chu=self.ghi_chu.text().strip(), parent=self)
        worker.tien_trinh.connect(self.status.setText)
        worker.xong.connect(self._xong)
        worker.hong.connect(self._hong)
        self._worker = worker
        worker.start()

    def _dung_video(self) -> None:
        """Ghép các ảnh đã duyệt của lượt gần nhất thành video ngắn.

        Danh sách nguồn đọc từ NHẬT KÝ trên đĩa chứ không từ những gì đang
        hiện trên màn hình: màn hình có thể là kết quả của lượt trước, còn
        nhật ký là thứ khớp với tệp thật.
        """
        from autodub import product_video

        if self._worker_video is not None and self._worker_video.isRunning():
            TOASTS.warn("Đang ghép video — chờ lượt này xong đã.")
            return

        duoc, ly_do = product_video.duoc_dung_video()
        if not duoc:
            TOASTS.warn(ly_do)
            return

        thu_muc = self._thu_muc_ket_qua or self._thu_muc_ra()
        anh = self._anh_nguon(thu_muc)
        if anh is None:
            return
        if not anh:
            TOASTS.warn("Chưa có ảnh nào đăng bán được để ghép. Dựng ảnh trước đã.")
            return

        ra = os.path.join(thu_muc, "video_san_pham.mp4")
        self.btn_video.setEnabled(False)
        self.status.setText(f"Đang ghép {len(anh)} ảnh thành video…")

        worker = ProductVideoWorker(anh, ra, parent=self)
        # Kiểm liên tục (C7) chạy TRONG worker rồi bắn cảnh báo ngược lên —
        # đây là CẢNH BÁO, không phải cổng chặn: video vẫn ghép, quyền quyết
        # định giữ hay dựng lại cảnh lạc là của người bán.
        worker.canh_bao.connect(self._canh_bao_lien_tuc)
        worker.xong.connect(self._video_xong)
        worker.hong.connect(self._video_hong)
        self._worker_video = worker
        worker.start()

    def _anh_nguon(self, thu_muc: str) -> list | None:
        """Danh sách ảnh sẽ vào video, ĐÚNG THỨ TỰ người dùng đã kéo.

        Trả ``None`` nghĩa là đã báo người dùng và không chạy tiếp.

        Đọc lại nhật ký ngay tại đây chứ không tin những gì danh sách đang
        hiện: giữa lúc nạp danh sách và lúc bấm ghép, một lượt dựng khác có
        thể đã lật phán quyết của chính tấm ảnh đó.

        Ảnh đã chọn mà nay không còn đăng bán được thì **vẫn đi xuống** —
        không lặng lẽ bỏ ra. Bỏ ra là xuất một video thiếu cảnh mà không ai
        biết; đi xuống thì lớp kiểm cuối chặn cả lượt và nói rõ ảnh nào,
        vì sao.
        """
        from autodub import product_video

        tat_ca = product_video.doc_nhat_ky(thu_muc)
        theo_duong = {a.duong_dan: a for a in tat_ca}
        chon = self._thu_tu_da_chon()

        if self.thu_tu.count() and not chon:
            TOASTS.warn("Chưa chọn cảnh nào — tích ít nhất một ảnh.")
            return None
        if not chon:
            # Chưa nạp danh sách (vd mở app rồi ghép luôn thư mục cũ): giữ
            # nguyên nếp cũ, lấy mọi ảnh đăng bán được theo thứ tự nhật ký.
            return [a for a in tat_ca if a.dung_duoc]

        ra = []
        for duong in chon:
            co = theo_duong.get(duong)
            ra.append(co if co is not None else product_video.AnhNguon(
                duong_dan=duong, boi_canh="", ket_luan="",
                ly_do="không còn trong nhật ký ảnh đã dựng",
                da_kiem=False, da_dong_nhan=False, bam_luc_kiem=""))
        return ra

    def _thu_tu_da_chon(self) -> list[str]:
        """Đường dẫn các ảnh còn tích, theo đúng thứ tự đang hiện."""
        ra = []
        for i in range(self.thu_tu.count()):
            muc = self.thu_tu.item(i)
            if muc.checkState() == Qt.CheckState.Checked:
                ra.append(str(muc.data(Qt.ItemDataRole.UserRole) or ""))
        return ra

    def _nap_thu_tu(self, thu_muc: str) -> None:
        """Nạp lại danh sách thứ tự từ nhật ký của thư mục vừa dựng."""
        from autodub import product_video

        self.thu_tu.clear()
        for a in product_video.doc_nhat_ky(thu_muc):
            if not a.dung_duoc:
                continue
            ten = dict(BOI_CANH).get(a.boi_canh, a.boi_canh or "—")
            muc = QListWidgetItem(f"{ten} — {os.path.basename(a.duong_dan)}")
            muc.setData(Qt.ItemDataRole.UserRole, a.duong_dan)
            muc.setFlags(muc.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            muc.setCheckState(Qt.CheckState.Checked)
            self.thu_tu.addItem(muc)

    def _goi_y_kich_ban(self) -> None:
        """Xin gợi ý câu dẫn cho từng cảnh, in ra Nhật ký để người dùng chép.

        Cố ý KHÔNG dán thẳng vào video: câu chữ bán hàng là thứ người bán
        chịu trách nhiệm trước sàn, không phải mô hình.
        """
        from autodub import product_video

        thu_muc = self._thu_muc_ket_qua or self._thu_muc_ra()
        anh = [a for a in product_video.doc_nhat_ky(thu_muc) if a.dung_duoc]
        if not anh:
            TOASTS.warn("Chưa có ảnh nào đăng bán được. Dựng ảnh trước đã.")
            return
        if self._worker_kich_ban is not None and self._worker_kich_ban.isRunning():
            TOASTS.warn("Đang xin gợi ý — chờ chút.")
            return

        self._anh_kich_ban = anh
        self.btn_kich_ban.setEnabled(False)
        self.log.append_log("Đang xin gợi ý kịch bản…", 20)
        worker = SceneScriptWorker(anh, self.ghi_chu.text().strip(), parent=self)
        worker.xong.connect(self._kich_ban_xong)
        self._worker_kich_ban = worker
        worker.start()

    def _kich_ban_xong(self, goi_y: list) -> None:
        self.btn_kich_ban.setEnabled(True)
        if not goi_y:
            TOASTS.warn("Chưa lấy được gợi ý — thử lại sau ít phút.")
            return
        anh = self._anh_kich_ban
        self.log.append_log("Gợi ý kịch bản (chỉ để tham khảo):", 20)
        for i, (cau, nhip) in enumerate(goi_y, 1):
            ten = dict(BOI_CANH).get(anh[i - 1].boi_canh, anh[i - 1].boi_canh) \
                if i <= len(anh) else ""
            self.log.append_log(f"  Cảnh {i} ({ten}): «{cau}» — {nhip}", 20)

    def _canh_bao_lien_tuc(self, ly_do: str) -> None:
        self.log.append_log(f"Các cảnh chưa liền mạch — {ly_do}. Video vẫn "
                            "ghép được; muốn mượt hơn thì dựng lại cảnh đó "
                            "rồi ghép lại.", 30)

    def _video_xong(self, duong: str) -> None:
        self.btn_video.setEnabled(True)
        self.status.setText(f"Đã xuất video: {duong}")
        TOASTS.success("Đã dựng xong video ngắn.")

    def _video_hong(self, loi: str) -> None:
        self.btn_video.setEnabled(True)
        # In NGUYÊN VĂN lý do: khi bị chặn, câu này liệt kê đúng ảnh nào và vì
        # sao — rút gọn đi thì người dùng không biết sửa cái gì.
        self.status.setText(loi)
        TOASTS.error(loi)

    def _mo_thu_muc(self) -> None:
        if self._thu_muc_ket_qua:
            open_folder(self._thu_muc_ket_qua)

    # ------------------------------------------------------------ kết quả --
    def _xoa_ket_qua(self) -> None:
        while self.ket_qua.count():
            muc = self.ket_qua.takeAt(0)
            w = muc.widget()
            if w is not None:
                w.deleteLater()

    def _xong(self, phien) -> None:
        self.btn_run.setEnabled(True)
        self.btn_open.setEnabled(True)
        if self._thu_muc_ket_qua:
            self._nap_thu_tu(self._thu_muc_ket_qua)
        if not phien.ket_qua:
            self.status.setText("Không dựng được ảnh nào — thử lại sau ít phút.")
            return

        for i, k in enumerate(phien.ket_qua):
            self.ket_qua.addWidget(self._the_anh(k), i // _COT, i % _COT)

        tong = len(phien.ket_qua)
        dung_duoc = phien.so_dung_duoc
        if dung_duoc == tong:
            self.status.setText(
                f"Xong {tong} ảnh — cả {tong} ảnh giữ nguyên sản phẩm, "
                "đăng bán được.")
        else:
            # Nói rõ CON SỐ nào không dùng được, đừng để người bán tự đếm
            # rồi đoán nhầm là tất cả đều an toàn.
            self.status.setText(
                f"Xong {tong} ảnh — {dung_duoc} ảnh đăng bán được, "
                f"{tong - dung_duoc} ảnh CHỈ để tham khảo (xem lý do dưới "
                "từng ảnh).")

    def _the_anh(self, ket) -> QWidget:
        """Một ô kết quả: ảnh, huy hiệu phán quyết, lý do bằng lời."""
        the = Card(padding=tokens.SP_3, spacing=tokens.SP_2)

        anh = QLabel()
        anh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(ket.duong_dan)
        if not pix.isNull():
            anh.setPixmap(pix.scaledToWidth(
                _ANH_W, Qt.TransformationMode.SmoothTransformation))
        else:
            anh.setText("(không mở được ảnh)")
        the.body.addWidget(anh)

        ten = dict(BOI_CANH).get(ket.boi_canh, ket.boi_canh)
        nhan_ten = QLabel(ten)
        nhan_ten.setObjectName("cardTitle")
        the.body.addWidget(nhan_ten)

        if ket.dung_duoc_de_ban:
            huy = StatusBadge("Đăng bán được", "success")
        elif not ket.da_kiem:
            huy = StatusBadge("Chưa kiểm được", "warning")
        else:
            huy = StatusBadge("Chỉ để tham khảo", "error")
        the.body.addWidget(huy)

        ly_do = QLabel(ket.ly_do or "—")
        ly_do.setWordWrap(True)
        ly_do.setObjectName("hint")
        ly_do.setMaximumWidth(_ANH_W)
        the.body.addWidget(ly_do)
        return the

    def _hong(self, loi: str) -> None:
        self.btn_run.setEnabled(True)
        self.status.setText(loi)
        TOASTS.error(loi)
