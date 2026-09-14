"""Dải điều hướng Phase H: Phân tích cấu trúc → Viết kịch bản → Dựng video.

Mini-spec H5 (14/09/2026).

**Vấn đề nó giải.** Ba trang của Phase H có thật, nhưng «Viết kịch bản» và
«Dựng video» KHÔNG nằm trên thanh bên (thanh bên đã kín ở màn 1080p, có
`tests/test_sidebar_no_overlap.py` canh). Người dùng chỉ đi tiếp được bằng nút
ở trang trước; đóng hoặc đổi trang là mất đường quay lại, và không lúc nào
nhìn thấy cả chuỗi. Chủ dự án báo đúng cảm nhận đó ngày 14/09: *"nó đang bị
thiếu quy trình"*.

**Nó KHÔNG phải cái gì.** Không phải cổng. Mở được trang H4 ≠ dựng được video:
cổng nằm ở tầng hàm (`autodub.storyboard.dung_storyboard` ném
`KichBanChuaDungDuoc` khi kịch bản chưa `ready`), và dải này không đụng tới.
Cho mở trang để người dùng BIẾT mình còn thiếu gì là việc khác hẳn với cho đi
tiếp — gộp hai thứ đó lại chính là cách một dải điều hướng biến thành lỗ hổng.

Dựng trên `ui.stepper.Stepper` sẵn có (`compact=True`, `tu_do_nhay=True`) thay
vì viết một thanh mới: bản sao thứ ba của cùng một thứ là bản sao sẽ trôi lệch.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from autodub_gui import tokens
from autodub_gui.ui.stepper import Stepper

#: Nhãn người dùng đọc được, đúng tên ba trang trên thanh điều hướng.
NHAN_BUOC = ["Phân tích cấu trúc", "Viết kịch bản", "Dựng video"]

BUOC_H2, BUOC_H3, BUOC_H4 = 0, 1, 2


class PhaseHRibbon(QWidget):
    """Dải ba bước + một dòng nói bước sau còn thiếu gì.

    ``buoc_duoc_chon`` phát chỉ số bước (0/1/2); trang chủ nối nó vào
    `switch_page` sẵn có — KHÔNG dựng cơ chế chuyển trang thứ hai.
    """

    buoc_duoc_chon = Signal(int)

    def __init__(self, buoc_hien_tai: int, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, tokens.SP_2)
        root.setSpacing(tokens.SP_1)

        self.stepper = Stepper(NHAN_BUOC, compact=True, tu_do_nhay=True)
        self.stepper.set_current(buoc_hien_tai)
        # Bước nào cũng bấm được: người dùng phải mở được H4 để biết còn
        # thiếu gì. `set_max_reached` cho phần vẽ hiểu các bước trước đã đi
        # qua, không phải để mở khoá — `tu_do_nhay` mới là thứ mở khoá.
        self.stepper.set_max_reached(len(NHAN_BUOC) - 1)
        self.stepper.step_clicked.connect(self._bam_buoc)
        root.addWidget(self.stepper)

        self.dong_trang_thai = QLabel("")
        self.dong_trang_thai.setObjectName("hint")
        self.dong_trang_thai.setWordWrap(True)
        root.addWidget(self.dong_trang_thai)

        self._buoc = buoc_hien_tai

    def _bam_buoc(self, chi_so: int) -> None:
        # Bấm lại chính bước đang xem thì không phát tín hiệu: chuyển sang
        # chính mình là một lượt dựng lại trang vô ích, và ở H2/H4 nó còn làm
        # mất thứ người dùng đang chọn dở.
        if chi_so != self._buoc:
            self.buoc_duoc_chon.emit(chi_so)

    def dat_trang_thai(self, cau: str) -> None:
        """Một dòng ngắn nói bước SAU cần gì. Rỗng thì ẩn hẳn dòng đó."""
        self.dong_trang_thai.setText(cau or "")
        self.dong_trang_thai.setVisible(bool(cau))
