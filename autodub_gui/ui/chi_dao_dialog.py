"""Hộp thoại «Chỉ đạo hình ảnh» — MINI-SPEC I3.

Vì sao là HỘP THOẠI chứ không phải một trang mới: thanh bên đã KÍN ở màn
1080p (bài học H3 — thêm mục thứ 21 làm tràn 45px), và bản chỉ đạo là thứ
đọc theo từng kịch bản chứ không phải một nơi làm việc riêng.

Từ I4 hộp thoại **sửa được** nhóm `transition` — nhóm DUY NHẤT khâu ghép
hình thực thi được. Danh sách mã lấy từ máy chủ chứ không gõ sẵn vào app:
chép tay một từ điển đang tiến hoá là dựng ra nguồn sự thật thứ hai, và nó
lệch im lặng đúng vào ngày catalog lên phiên bản mới.

Vẫn KHÔNG có nút «Áp dụng» / «Render» / «Sinh ảnh» / «Dựng video». Lý do cũ
("luồng dựng chưa đọc bản chỉ đạo") đã hết hiệu lực từ I5 — nhưng lý do mới
vẫn giữ nguyên kết luận: dựng video là việc của trang «Dựng video», và một
cái nút ở đây chỉ hứa hộ cho một trang khác. Có test canh để nó không mọc
lại, và các nhóm còn lại vẫn chỉ đọc vì máy không dựng được chúng.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.chi_dao_text import (
    cau_trang_thai, cau_ty_le, dong_cho_doan, mo_ta_loai, nhan_muc,
)
from autodub_gui.ui.buttons import GhostButton

_MIN_W = 640
_MIN_H = 520


class _DongDoan(QFrame):
    """Một đoạn: số thứ tự, các mã đã chọn, và câu lý do."""

    def __init__(self, doan: dict, muc_chuyen: list | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._doan = doan
        self.o_chuyen: QComboBox | None = None
        self.setStyleSheet(
            f"QFrame {{ background: {tokens.BG_PANEL}; "
            f"border: 1px solid {tokens.BORDER_DEFAULT}; "
            f"border-radius: {tokens.RADIUS_LG}px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(tokens.SP_3, tokens.SP_3, tokens.SP_3, tokens.SP_3)
        lay.setSpacing(tokens.SP_1)

        tieu_de = QLabel(f"Đoạn {doan.get('thuTu')}")
        tieu_de.setObjectName("sectionTitle")
        lay.addWidget(tieu_de)

        for c in (doan.get("chon") or []):
            hang = QLabel(f"{nhan_muc(c)} — {mo_ta_loai(c)}")
            hang.setWordWrap(True)
            # Hai loại, hai `objectName` khác nhau: khác nhau bằng MÀU nữa,
            # nhưng chữ ở `nhan_muc()` mới là thứ nói ra sự khác biệt.
            hang.setObjectName("hint" if c.get("laGoiY", True) else "sectionTitle")
            lay.addWidget(hang)

        if not (doan.get("chon") or []):
            trong = QLabel(dong_cho_doan(doan)[0])
            trong.setObjectName("hint")
            lay.addWidget(trong)

        # I4 — chỉ nhóm `transition` sửa được: nó là nhóm DUY NHẤT khâu ghép
        # hình thực thi được. Cho sửa các nhóm khác là mời người dùng chỉnh
        # một thứ không ai đọc.
        if muc_chuyen:
            hang_sua = QHBoxLayout()
            hang_sua.setSpacing(tokens.SP_2)
            nhan_o = QLabel("Chuyển cảnh:")
            nhan_o.setObjectName("hint")
            hang_sua.addWidget(nhan_o)
            self.o_chuyen = QComboBox()
            # Mục đầu = bỏ trống. Giữ được lựa chọn "không chỉ định" là cách
            # duy nhất để nếp thương hiệu (I6) còn chỗ phát huy.
            self.o_chuyen.addItem("— không chỉ định —", "")
            for m in muc_chuyen:
                self.o_chuyen.addItem(m["nhan"], m["ma"])
            hien = next((c["ma"] for c in (doan.get("chon") or [])
                         if c.get("nhom") == "transition"), "")
            vi_tri = self.o_chuyen.findData(hien)
            self.o_chuyen.setCurrentIndex(vi_tri if vi_tri >= 0 else 0)
            hang_sua.addWidget(self.o_chuyen, 1)
            lay.addLayout(hang_sua)

        ly_do = str(doan.get("lyDo") or "").strip()
        if ly_do:
            nhan = QLabel(f"Vì sao: {ly_do}")
            nhan.setObjectName("hint")
            nhan.setWordWrap(True)
            lay.addWidget(nhan)


class ChiDaoHinhAnhDialog(QDialog):
    """Xem bản chỉ đạo hình ảnh của một kịch bản. CHỈ ĐỌC."""

    def __init__(self, ban: dict, parent: QWidget | None = None, *,
                 muc_chuyen: list | None = None, on_luu=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉ đạo hình ảnh")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self._ban = ban or {}
        # Không có danh sách mã từ máy chủ thì KHÔNG dựng ô sửa: thà chỉ đọc
        # như trước còn hơn hiện một ô rỗng rồi lưu về một bản trống trơn.
        self._muc_chuyen = list(muc_chuyen or [])
        self._on_luu = on_luu
        self._dong: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(tokens.SP_4, tokens.SP_4, tokens.SP_4, tokens.SP_4)
        lay.setSpacing(tokens.SP_3)

        self.lbl_ty_le = QLabel(cau_ty_le(self._ban))
        self.lbl_ty_le.setWordWrap(True)
        lay.addWidget(self.lbl_ty_le)

        cu = cau_trang_thai(self._ban)
        if cu:
            self.lbl_cu = QLabel(cu)
            self.lbl_cu.setObjectName("hint")
            self.lbl_cu.setWordWrap(True)
            lay.addWidget(self.lbl_cu)

        vung = QScrollArea()
        vung.setWidgetResizable(True)
        vung.setFrameShape(QFrame.NoFrame)
        trong = QWidget()
        trong_lay = QVBoxLayout(trong)
        trong_lay.setContentsMargins(0, 0, 0, 0)
        trong_lay.setSpacing(tokens.SP_2)
        for d in (self._ban.get("doan") or []):
            dong = _DongDoan(d, self._muc_chuyen if self._sua_duoc() else None)
            self._dong.append(dong)
            trong_lay.addWidget(dong)
        trong_lay.addStretch()
        vung.setWidget(trong)
        lay.addWidget(vung, 1)

        cuoi = QHBoxLayout()
        self.lbl_luu = QLabel("")
        self.lbl_luu.setObjectName("hint")
        self.lbl_luu.setWordWrap(True)
        cuoi.addWidget(self.lbl_luu, 1)
        cuoi.addStretch()
        if self._sua_duoc():
            self.btn_luu = GhostButton("Lưu chỉnh sửa")
            self.btn_luu.clicked.connect(self._luu)
            cuoi.addWidget(self.btn_luu)
        self.btn_dong = GhostButton("Đóng")
        self.btn_dong.clicked.connect(self.accept)
        cuoi.addWidget(self.btn_dong)
        lay.addLayout(cuoi)

    def _sua_duoc(self) -> bool:
        """Sửa được khi có danh sách mã, có chỗ lưu, và bản còn khớp kịch bản.

        Bản đã cũ thì KHÔNG cho sửa: nó nói về một kịch bản khác, nên sửa nó
        là chỉnh chuyển cảnh cho những đoạn không còn tồn tại.
        """
        return bool(self._muc_chuyen and self._on_luu
                    and not self._ban.get("laCu"))

    def doan_dang_chon(self) -> list:
        """Bản chỉ đạo theo đúng thứ đang hiện trên màn — để test đọc được."""
        ra = []
        for dong in self._dong:
            goc = dong._doan
            # CHỈ `nhom` + `ma`. `nhan`/`laGoiY`/`dung` là thứ máy chủ tính
            # từ catalog — mang chúng theo là để client tự phong cho một mã
            # khả năng mà khâu dựng không có. Thu hẹp ngay tại NGUỒN chứ
            # không trông vào lớp thu hẹp ở `saas_client`: một chỗ thu hẹp
            # thì còn quên được, hai chỗ cùng nói một luật thì lệch nhau.
            giu = [{"nhom": c["nhom"], "ma": c["ma"]}
                   for c in (goc.get("chon") or [])
                   if c.get("nhom") != "transition"]
            ma = dong.o_chuyen.currentData() if dong.o_chuyen else None
            if ma is None:
                ma = next((c["ma"] for c in (goc.get("chon") or [])
                           if c.get("nhom") == "transition"), "")
            if ma:
                giu.append({"nhom": "transition", "ma": ma})
            ra.append({"thuTu": goc.get("thuTu"), "chon": giu})
        return ra

    def _luu(self) -> None:
        """Giao việc lưu cho bên gọi. KHÔNG tự báo thành công.

        Bên gọi chạy lượt ghi ở luồng nền, nên viết "Đã lưu" ngay tại đây là
        báo thành công trước khi biết máy chủ nhận hay từ chối — đúng lớp lỗi
        mà cả dự án này đã dính nhiều lần. Kết quả thật về qua `bao_ket_qua`.
        """
        self.btn_luu.setEnabled(False)
        self.lbl_luu.setText("Đang lưu…")
        try:
            self._on_luu(self.doan_dang_chon())
        except Exception as e:   # noqa: BLE001 — lý do phải tới người dùng
            self.bao_ket_qua(False, str(e))

    def bao_ket_qua(self, ok: bool, thong_diep: str = "") -> None:
        """Bên gọi báo ngược kết quả lượt ghi thật."""
        self.btn_luu.setEnabled(True)
        self.lbl_luu.setText(
            "Đã lưu. Lượt dựng sau sẽ dùng thứ này."
            if ok else f"Chưa lưu được: {thong_diep}")

    def chu_hien_ra(self) -> str:
        """Toàn bộ chữ đang hiện — để test đọc được mà không cần chụp màn."""
        return "\n".join(
            w.text() for w in self.findChildren(QLabel) if w.text())
