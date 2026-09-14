"""Thanh sáu bước lưỡng dụng.

Trước khi chạy, người dùng bấm vào số để nhảy giữa các bước cấu hình.
Trong khi chạy, các bước phản ánh tiến độ thật của quá trình xử lý.

Mỗi bước có ba trạng thái: đã xong, đang ở đây và chưa tới.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from autodub_gui import tokens

DONE, CURRENT, UPCOMING = "done", "current", "upcoming"

_CIRCLE = 30
_LINE_W = 2
_GLOW = 4
_LABEL_GAP = 8
_HEIGHT = 76

#: Chế độ GỌN — mini-spec H5. Dải điều hướng Phase H nằm ở đầu CẢ BA trang
#: H2/H3/H4, nên 76px mỗi trang là cái giá phải trả ba lần cho một thanh chỉ
#: đường. Hai chỗ dùng sẵn (`new_project_page`, `setup_wizard`) KHÔNG truyền
#: `compact` nên giữ nguyên kích thước cũ — thêm chế độ, không đổi mặc định.
_CIRCLE_GON = 20
_HEIGHT_GON = 46
_CHECK_PEN = 2.0
_GLOW_ALPHA = 56

_DONE_BG = tokens.STEP_DONE_BG
_UPCOMING_BG = tokens.STEP_UPCOMING_BG
_UPCOMING_TEXT = tokens.STEP_UPCOMING_TEXT


class Stepper(QWidget):
    """Dãy các bước nối nhau bằng đường kẻ ngang."""

    step_clicked = Signal(int)      # chỉ số bước, đếm từ 0

    def __init__(self, labels: list[str], parent: QWidget | None = None, *,
                 compact: bool = False, tu_do_nhay: bool = False):
        """``compact``: bản thấp cho dải điều hướng (H5).

        ``tu_do_nhay``: cho phép bấm MỌI bước, không theo luật "chỉ tới bước
        kế tiếp bước xa nhất". Dải Phase H cần điều này — người dùng phải mở
        được H4 để BIẾT mình còn thiếu gì, kể cả khi chưa có kịch bản. Mở
        trang không phải là mở cổng: cổng dựng video nằm ở tầng hàm
        (`dung_storyboard`), không ở đây.
        """
        super().__init__(parent)
        self._labels = list(labels)
        self._current = 0
        self._max_reached = 0
        self._live = False
        self._live_done: set[int] = set()
        self._compact = bool(compact)
        self._tu_do_nhay = bool(tu_do_nhay)
        self.setMinimumHeight(_HEIGHT_GON if self._compact else _HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._hover = -1

    # -- Trạng thái ----------------------------------------------------
    def current_step(self) -> int:
        return self._current

    def set_current(self, index: int) -> None:
        """Đặt bước đang xem, đồng thời ghi nhận bước xa nhất đã tới."""
        index = max(0, min(index, len(self._labels) - 1))
        self._current = index
        self._max_reached = max(self._max_reached, index)
        self.update()

    def set_max_reached(self, index: int) -> None:
        """Bước xa nhất người dùng đã hoàn tất, dùng để giới hạn phạm vi nhảy."""
        self._max_reached = max(0, min(index, len(self._labels) - 1))
        self.update()

    def set_live_mode(self, live: bool) -> None:
        """Bật chế độ bám theo tiến trình thật và khóa việc bấm chọn."""
        self._live = live
        self._live_done.clear()
        self.setCursor(Qt.CursorShape.ArrowCursor if live
                       else Qt.CursorShape.PointingHandCursor)
        self.update()

    def set_live_progress(self, index: int) -> None:
        """Đánh dấu bước đang chạy; mọi bước trước đó coi như đã xong."""
        index = max(0, min(index, len(self._labels) - 1))
        self._live_done = set(range(index))
        self._current = index
        self.update()

    def mark_all_done(self) -> None:
        """Đánh dấu toàn bộ các bước đã hoàn tất."""
        self._live_done = set(range(len(self._labels)))
        self._current = len(self._labels) - 1
        self.update()

    def _duong_kinh(self) -> int:
        return _CIRCLE_GON if self._compact else _CIRCLE

    def state_of(self, index: int) -> str:
        """Trạng thái hiện tại của một bước."""
        if self._live:
            if index in self._live_done:
                return DONE
            return CURRENT if index == self._current else UPCOMING
        if index < self._current:
            return DONE
        return CURRENT if index == self._current else UPCOMING

    def can_jump_to(self, index: int) -> bool:
        """Chỉ cho phép nhảy tới bước kế tiếp bước xa nhất đã hoàn tất.

        `tu_do_nhay` bỏ luật này (H5) — xem `__init__`. Luật cũ giữ nguyên cho
        hai chỗ đang dùng, vì trình hướng dẫn cài đặt thì nhảy vượt bước là vô
        nghĩa thật.
        """
        if self._live:
            return False
        if self._tu_do_nhay:
            return 0 <= index < len(self._labels)
        return 0 <= index <= self._max_reached + 1

    # -- Tương tác -----------------------------------------------------
    def _index_at(self, x: float) -> int:
        if not self._labels:
            return -1
        slot = self.width() / len(self._labels)
        index = int(x // slot) if slot else -1
        return index if 0 <= index < len(self._labels) else -1

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 — theo quy ước của Qt
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            label = self._labels[index] if index >= 0 else ""
            self.setToolTip(f"Bước {index + 1}: {label}" if index >= 0 else "")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 — theo quy ước của Qt
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 — theo quy ước của Qt
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._index_at(event.position().x())
            if index >= 0 and self.can_jump_to(index):
                self.step_clicked.emit(index)
        super().mousePressEvent(event)

    # -- Vẽ ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 — theo quy ước của Qt
        if not self._labels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        count = len(self._labels)
        slot = self.width() / count
        duong_kinh = self._duong_kinh()
        cy = _GLOW + duong_kinh / 2 + 2
        centers = [slot * (i + 0.5) for i in range(count)]

        self._paint_connectors(painter, centers, cy)
        for i, cx in enumerate(centers):
            self._paint_circle(painter, i, cx, cy)
            self._paint_label(painter, i, cx, cy, slot)
        painter.end()

    def _paint_connectors(self, painter: QPainter,
                          centers: list[float], cy: float) -> None:
        """Vẽ các đường nối giữa hai vòng tròn liền kề."""
        duong_kinh = self._duong_kinh()
        for i in range(len(centers) - 1):
            done = self.state_of(i) == DONE
            color = QColor(_DONE_BG if done else _UPCOMING_BG)
            painter.setPen(QPen(color, _LINE_W))
            painter.drawLine(int(centers[i] + duong_kinh / 2 + 4), int(cy),
                             int(centers[i + 1] - duong_kinh / 2 - 4), int(cy))

    def _paint_circle(self, painter: QPainter, index: int,
                      cx: float, cy: float) -> None:
        """Vẽ vòng tròn của một bước, kèm dấu tích nếu bước đó đã xong."""
        state = self.state_of(index)
        d = self._duong_kinh()
        rect = QRectF(cx - d / 2, cy - d / 2, d, d)
        if state == CURRENT:
            glow = QColor(tokens.PRIMARY)
            glow.setAlpha(_GLOW_ALPHA)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(rect.adjusted(-_GLOW, -_GLOW, _GLOW, _GLOW))
        fill = {DONE: _DONE_BG, CURRENT: tokens.PRIMARY,
                UPCOMING: _UPCOMING_BG}[state]
        painter.setBrush(QColor(fill))
        if index == self._hover and self.can_jump_to(index):
            painter.setPen(QPen(QColor(tokens.BORDER_ACTIVE), 1.5))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        if state == DONE:
            painter.setPen(QPen(QColor(tokens.TEXT_ON_ACCENT), _CHECK_PEN,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx - 6), int(cy), int(cx - 1), int(cy + 5))
            painter.drawLine(int(cx - 1), int(cy + 5), int(cx + 6), int(cy - 5))
        else:
            font = QFont(self.font())
            font.setPixelSize(tokens.FS_LABEL)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QColor(tokens.TEXT_ON_ACCENT if state == CURRENT
                                  else _UPCOMING_TEXT))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(index + 1))

    def _paint_label(self, painter: QPainter, index: int, cx: float,
                     cy: float, slot: float) -> None:
        """Vẽ tên bước bên dưới vòng tròn, rút gọn nếu không đủ chỗ."""
        state = self.state_of(index)
        color = (tokens.TEXT_PRIMARY if state == CURRENT
                 else tokens.TEXT_SECONDARY if state == DONE
                 else tokens.TEXT_MUTED)
        font = QFont(self.font())
        font.setPixelSize(tokens.FS_META)
        font.setWeight(QFont.Weight.DemiBold if state == CURRENT
                       else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(color))
        d = self._duong_kinh()
        cao = _HEIGHT_GON if self._compact else _HEIGHT
        rect = QRectF(cx - slot / 2 + 2, cy + d / 2 + _LABEL_GAP,
                      slot - 4, cao - cy - d / 2 - _LABEL_GAP)
        text = painter.fontMetrics().elidedText(
            self._labels[index], Qt.TextElideMode.ElideRight, int(rect.width()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter |
                         Qt.AlignmentFlag.AlignTop, text)
