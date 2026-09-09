"""Trang Hồ sơ Brand — mini-spec H1 (docs/PLAN.md, Phase H: Viral Flow Clone
& Brand Rewrite).

Nền tảng multi-tenant: MỘT máy (không có khái niệm "tài khoản" tách khỏi
thiết bị trong hệ thống này) có thể tạo NHIỀU hồ sơ brand — mỗi hồ sơ phục
vụ đúng một sản phẩm/khách hàng. Các tác vụ viết lại kịch bản (H3, chưa làm)
và dựng video (H4, chưa làm) sẽ đọc hồ sơ ở đây để biết "viết cho ai" mà
không cần người dùng gõ tay lại mỗi lần.

Toàn bộ dữ liệu nằm trên máy chủ (không có đường lui offline — Constraint 2
của H1 đòi hỏi dùng lại được qua nhiều lượt/nhiều thiết bị): mọi thao tác đi
qua `BrandProfileWorker`, KHÔNG chạy trên luồng giao diện (luật C7). Chưa
cấu hình máy chủ thì lỗi hiện ra là `OfflineError` sẵn có của
`saas_client.py` ("Chưa cấu hình địa chỉ máy chủ VoxDub."), không dựng thêm
một trạng thái rỗng riêng cho ca này — cùng cách trang Ảnh sản phẩm đang xử lý.

Không tự động điền trường nào từ dữ liệu suy luận (Constraint 3 của H1) —
người dùng tự gõ hoặc để trống, đúng nguyên tắc đã áp dụng cho gợi ý tên
nhân vật (`character_name`, không tự ghi vào hồ sơ).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout,
    QWidget,
)

from autodub_gui import icons, tokens
from autodub_gui.log_text import error_line
from autodub_gui.pages import BasePage
from autodub_gui.ui.buttons import GhostButton, IconButton, PrimaryButton
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.table import Column, DataTable
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import BrandProfileWorker

_ACTION_ICON = 28


class BrandProfileFormDialog(QDialog):
    """Form tạo/sửa MỘT hồ sơ brand — Scope A của H1 (đủ trường cho H3 đọc,
    không dựng thành trang quản lý phức tạp kiểu CRM)."""

    def __init__(self, parent: QWidget | None = None, *, profile: dict | None = None):
        super().__init__(parent)
        self._profile = profile   # None = tạo mới
        self.setWindowTitle("Sửa hồ sơ brand" if profile else "Tạo hồ sơ brand")
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_5, tokens.SP_5, tokens.SP_5, tokens.SP_5)
        root.setSpacing(tokens.SP_3)

        def truong(nhan: str, ban_dau: str = "", cao: int = 0) -> QWidget:
            root.addWidget(QLabel(nhan))
            if cao:
                o = QPlainTextEdit()
                o.setPlainText(ban_dau)
                o.setMaximumHeight(cao)
            else:
                o = QLineEdit(ban_dau)
            root.addWidget(o)
            return o

        p = profile or {}
        self.ten_brand = truong("Tên brand *", p.get("tenBrand", ""))
        self.mo_ta = truong("Sản phẩm / dịch vụ", p.get("moTaSanPham", ""), cao=70)
        self.doi_tuong = truong("Đối tượng khách", p.get("doiTuongKhach", ""), cao=50)
        self.tone = truong("Tone giọng (vd: hài hước, trang trọng, gần gũi)",
                           p.get("toneGiong", ""))
        self.usp = truong("Điểm bán hàng độc nhất (USP)", p.get("usp", ""), cao=50)

        root.addWidget(QLabel(
            "Ràng buộc KHÔNG được nói — mỗi dòng một điều "
            "(vd: không hứa công dụng y tế, không dùng từ \"tốt nhất/số một\"):"))
        self.rang_buoc = QPlainTextEdit(
            "\n".join(p.get("rangBuocKhongDuocNoi", [])))
        self.rang_buoc.setMaximumHeight(70)
        root.addWidget(self.rang_buoc)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_cancel = GhostButton("Huỷ")
        btn_cancel.clicked.connect(self.reject)
        self.btn_save = PrimaryButton("Lưu")
        self.btn_save.clicked.connect(self._on_save)
        actions.addWidget(btn_cancel)
        actions.addWidget(self.btn_save)
        root.addLayout(actions)

    def _on_save(self) -> None:
        if not self.ten_brand.text().strip():
            TOASTS.warn("Tên brand không được để trống.")
            return
        self.accept()

    def fields(self) -> dict:
        """Giá trị đã nhập, đúng khuôn tham số của `saas_client`.
        `rang_buoc_khong_duoc_noi` LUÔN có mặt (mảng, có thể rỗng) — Constraint
        2 của H1: người dùng đã đi qua ô này (thấy trên form), không lặng lẽ
        thiếu."""
        dong = [d.strip() for d in self.rang_buoc.toPlainText().splitlines()]
        return {
            "ten_brand": self.ten_brand.text().strip(),
            "mo_ta_san_pham": self.mo_ta.toPlainText().strip(),
            "doi_tuong_khach": self.doi_tuong.toPlainText().strip(),
            "tone_giong": self.tone.text().strip(),
            "usp": self.usp.toPlainText().strip(),
            "rang_buoc_khong_duoc_noi": [d for d in dong if d],
        }


class BrandProfilePage(BasePage):
    """Danh sách hồ sơ brand của máy này — tạo, sửa, xoá."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._profiles: list[dict] = []
        self._worker: BrandProfileWorker | None = None
        self._build()

    # -- Dựng giao diện --------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_6, tokens.SP_4, tokens.SP_6, tokens.SP_6)
        root.setSpacing(tokens.SP_3)

        title = QLabel("Hồ sơ Brand")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Mỗi hồ sơ mô tả MỘT sản phẩm/khách hàng: sản phẩm, đối tượng, "
            "tone giọng, điểm bán hàng và ràng buộc không được nói. Các tính "
            "năng viết kịch bản/dựng video tự động (đang xây) sẽ đọc hồ sơ "
            "này để biết viết cho ai — bạn không phải gõ lại thông tin mỗi lần.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_reload = GhostButton("Tải lại")
        self.btn_reload.clicked.connect(self._reload)
        self.btn_add = PrimaryButton("Thêm hồ sơ brand")
        self.btn_add.clicked.connect(self._on_add)
        actions.addWidget(self.btn_reload)
        actions.addWidget(self.btn_add)
        root.addLayout(actions)

        self.table = DataTable(
            [Column("Tên brand", stretch=True),
             Column("Đối tượng khách", stretch=True),
             Column("USP", stretch=True),
             Column("Thao tác", width=90)],
            empty_title="Chưa có hồ sơ brand nào",
            empty_description="Bấm «Thêm hồ sơ brand» để tạo hồ sơ đầu tiên.")
        root.addWidget(self.table, 1)

        self.log = LogPanel()
        self.log.setMaximumHeight(80)
        root.addWidget(self.log)

    # -- Vòng đời ---------------------------------------------------------
    def on_shown(self) -> None:
        self._reload()

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    # -- Dữ liệu ------------------------------------------------------------
    def _reload(self) -> None:
        if self.is_running():
            return
        self._set_running(True)
        worker = BrandProfileWorker("list", parent=self)
        worker.finished_ok.connect(self._on_worker_ok)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._set_running(False))
        self._worker = worker
        worker.start()

    def _set_running(self, running: bool) -> None:
        self.btn_reload.set_loading(running, "Đang tải…")
        self.btn_add.setEnabled(not running)

    def _on_worker_ok(self, action: str, ket) -> None:
        if action == "list":
            self._profiles = ket or []
            self._render_table()
        elif action == "create":
            TOASTS.success(f"Đã tạo hồ sơ «{ket.get('tenBrand', '')}».")
            self._reload()
        elif action == "update":
            TOASTS.success(f"Đã lưu hồ sơ «{ket.get('tenBrand', '')}».")
            self._reload()
        elif action == "delete":
            TOASTS.success("Đã xoá hồ sơ brand.")
            self._reload()

    def _on_worker_failed(self, action: str, message: str) -> None:
        text, level = error_line(message)
        self.log.append_log(text, level)
        nhan = {"list": "tải danh sách", "create": "tạo hồ sơ",
               "update": "lưu hồ sơ", "delete": "xoá hồ sơ"}.get(action, action)
        ConfirmDialog.show_error(self, f"Không {nhan} được",
                                 "Kiểm tra kết nối mạng rồi thử lại.",
                                 detail=message)

    def _render_table(self) -> None:
        self.table.clear_rows()
        for profile in self._profiles:
            row = self.table.add_row()
            self.table.set_widget(row, 0, QLabel(profile.get("tenBrand", "")))
            self.table.set_widget(row, 1, QLabel(profile.get("doiTuongKhach", "")))
            self.table.set_widget(row, 2, QLabel(profile.get("usp", "")))
            self.table.set_widgets(row, 3, self._actions(profile))
        self.table.auto_state()

    def _actions(self, profile: dict) -> list[QWidget]:
        edit = IconButton(icons.edit(tokens.TEXT_SECONDARY), "Sửa hồ sơ",
                          size=_ACTION_ICON)
        edit.clicked.connect(lambda _c=False, p=profile: self._on_edit(p))
        delete = IconButton(icons.trash(tokens.DANGER), "Xoá hồ sơ",
                            size=_ACTION_ICON)
        delete.clicked.connect(lambda _c=False, p=profile: self._on_delete(p))
        return [edit, delete]

    # -- Hành động ----------------------------------------------------------
    def _on_add(self) -> None:
        dialog = BrandProfileFormDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._set_running(True)
            worker = BrandProfileWorker("create", fields=dialog.fields(), parent=self)
            worker.finished_ok.connect(self._on_worker_ok)
            worker.failed.connect(self._on_worker_failed)
            worker.finished.connect(lambda: self._set_running(False))
            self._worker = worker
            worker.start()

    def _on_edit(self, profile: dict) -> None:
        dialog = BrandProfileFormDialog(self, profile=profile)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._set_running(True)
            worker = BrandProfileWorker(
                "update", profile_id=profile["id"], fields=dialog.fields(), parent=self)
            worker.finished_ok.connect(self._on_worker_ok)
            worker.failed.connect(self._on_worker_failed)
            worker.finished.connect(lambda: self._set_running(False))
            self._worker = worker
            worker.start()

    def _on_delete(self, profile: dict) -> None:
        confirmed, _ = ConfirmDialog.ask(
            self, "Xoá hồ sơ brand?",
            f"Xoá hồ sơ «{profile.get('tenBrand', '')}»? Các kịch bản/video đã "
            "dựng từ trước không bị xoá, nhưng sẽ không dùng lại được hồ sơ này nữa.",
            kind="warning", confirm_label="Xoá", cancel_label="Giữ lại")
        if not confirmed:
            return
        self._set_running(True)
        worker = BrandProfileWorker("delete", profile_id=profile["id"], parent=self)
        worker.finished_ok.connect(self._on_worker_ok)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._set_running(False))
        self._worker = worker
        worker.start()

    def shutdown(self) -> None:
        if self.is_running():
            self._worker.wait(5000)
