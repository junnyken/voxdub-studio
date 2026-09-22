"""Hộp thoại «Chỉ đạo hình ảnh» — MINI-SPEC I3.

Vì sao là HỘP THOẠI chứ không phải một trang mới: thanh bên đã KÍN ở màn
1080p (bài học H3 — thêm mục thứ 21 làm tràn 45px), và bản chỉ đạo là thứ
đọc theo từng kịch bản chứ không phải một nơi làm việc riêng.

Vì sao **chỉ đọc**, không có nút «Áp dụng» / «Render» / «Sinh ảnh»: luồng
«Dựng video» hôm nay chưa đọc bản chỉ đạo (việc của I5), và phần lớn mục là
gợi ý cho người chứ không phải lệnh cho máy. Một cái nút hứa nhiều hơn thứ
làm được là đúng lớp lỗi #5 của dự án — nên ở đây không có cái nút đó, và có
test canh để nó không mọc lại.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
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

    def __init__(self, doan: dict, parent: QWidget | None = None):
        super().__init__(parent)
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

        ly_do = str(doan.get("lyDo") or "").strip()
        if ly_do:
            nhan = QLabel(f"Vì sao: {ly_do}")
            nhan.setObjectName("hint")
            nhan.setWordWrap(True)
            lay.addWidget(nhan)


class ChiDaoHinhAnhDialog(QDialog):
    """Xem bản chỉ đạo hình ảnh của một kịch bản. CHỈ ĐỌC."""

    def __init__(self, ban: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Chỉ đạo hình ảnh")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self._ban = ban or {}

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
            trong_lay.addWidget(_DongDoan(d))
        trong_lay.addStretch()
        vung.setWidget(trong)
        lay.addWidget(vung, 1)

        cuoi = QHBoxLayout()
        cuoi.addStretch()
        # ĐÚNG MỘT nút, và nó chỉ đóng cửa sổ. Xem docstring đầu tệp.
        self.btn_dong = GhostButton("Đóng")
        self.btn_dong.clicked.connect(self.accept)
        cuoi.addWidget(self.btn_dong)
        lay.addLayout(cuoi)

    def chu_hien_ra(self) -> str:
        """Toàn bộ chữ đang hiện — để test đọc được mà không cần chụp màn."""
        return "\n".join(
            w.text() for w in self.findChildren(QLabel) if w.text())
