"""Trang quản lý hồ sơ nhân vật (mini-spec V62).

V57–V61 dựng xong phần máy: nhân vật được nhận lại qua các tập bằng embedding
giọng. Nhưng muốn đổi tên `SPEAKER_00` thành «Lý Tứ» hay sửa giọng cho một
nhân vật thì vẫn phải mở file JSON bằng tay — với series dài, đó là thứ chạm
vào hằng ngày.

Phạm vi CỐ Ý hẹp: xem, đổi tên, đổi giọng, xoá nhân vật, và sửa quy ước dịch
của series. KHÔNG có tạo hồ sơ ở đây — hồ sơ sinh ra khi dub tập đầu (gõ tên
ở trang Tạo dự án), tạo rỗng ở đây chỉ đẻ thêm hồ sơ trống không ai dùng.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from autodub_gui import tokens
from autodub_gui.pages.tool_page_base import BasePage
from autodub_gui.ui.buttons import DangerButton, GhostButton, PrimaryButton
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.toast import TOASTS

COL_NAME, COL_VOICE, COL_EPISODES, COL_MATCH = range(4)


class CharacterPage(BasePage):
    """Xem và sửa hồ sơ nhân vật của từng series."""

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._profile = None
        self._build()
        self.reload()

    # ------------------------------------------------------------ dựng UI --

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_6, tokens.SP_4, tokens.SP_6, tokens.SP_6)
        root.setSpacing(tokens.SP_3)

        title = QLabel("Hồ sơ nhân vật")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Mỗi series một hồ sơ: nhân vật đã gặp ở tập trước sẽ nhận lại "
            "đúng giọng cũ. Đổi tên nhân vật ở đây cho dễ nhớ, đổi giọng thì "
            "tập sau dùng giọng mới.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        picker = QHBoxLayout()
        picker.setSpacing(tokens.SP_2)
        picker.addWidget(QLabel("Series:"))
        self.profile_picker = QComboBox()
        self.profile_picker.currentTextChanged.connect(self._on_profile_changed)
        picker.addWidget(self.profile_picker, 1)
        self.btn_reload = GhostButton("Tải lại")
        self.btn_reload.clicked.connect(self.reload)
        picker.addWidget(self.btn_reload)
        root.addLayout(picker)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Nhân vật", "Giọng đọc", "Số tập", "Nhận diện"])
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_VOICE, QHeaderView.Stretch)
        # Số tập và cách nhận diện là thông tin ĐỌC, không sửa được: chúng do
        # hệ thống đo ra, gõ tay vào đó chỉ tạo dữ liệu sai.
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        # Theo dõi sửa đổi chưa lưu — xem `_on_profile_changed`.
        self.table.itemChanged.connect(self._mark_dirty)
        root.addWidget(self.table, 1)

        self.empty_note = QLabel(
            "Chưa có hồ sơ nào. Hồ sơ được tạo khi bạn điền tên series ở "
            "trang Tạo dự án và chạy tập đầu tiên.")
        self.empty_note.setObjectName("hint")
        self.empty_note.setWordWrap(True)
        root.addWidget(self.empty_note)

        self._dirty = False
        self._loading = False

        root.addWidget(QLabel("Quy ước dịch của series (đè cài đặt chung):"))
        self.pronouns = QPlainTextEdit()
        self.pronouns.setPlaceholderText("Cách xưng hô, vd: tôi – anh")
        self.pronouns.setMaximumHeight(60)
        self.pronouns.textChanged.connect(self._mark_dirty)
        root.addWidget(self.pronouns)
        self.glossary = QPlainTextEdit()
        self.glossary.setPlaceholderText("Thuật ngữ cố định, mỗi dòng «gốc = dịch»")
        self.glossary.setMaximumHeight(80)
        self.glossary.textChanged.connect(self._mark_dirty)
        root.addWidget(self.glossary)

        footer = QHBoxLayout()
        self.btn_delete = DangerButton("Xoá nhân vật đang chọn")
        self.btn_delete.clicked.connect(self._delete_selected)
        footer.addWidget(self.btn_delete)
        footer.addStretch()
        self.btn_save = PrimaryButton("Lưu hồ sơ")
        self.btn_save.clicked.connect(self._save)
        footer.addWidget(self.btn_save)
        root.addLayout(footer)

    # ------------------------------------------------------------ dữ liệu --

    def _profiles_dir(self) -> str:
        from autodub.pipeline import DubPipeline
        return DubPipeline._profiles_dir(self._settings_provider())

    def reload(self) -> None:
        """Nạp lại danh sách hồ sơ từ đĩa."""
        from autodub.character_profile import list_profiles

        current = self.profile_picker.currentText()
        names = list_profiles(self._profiles_dir())

        self.profile_picker.blockSignals(True)
        self.profile_picker.clear()
        self.profile_picker.addItems(names)
        if current in names:
            self.profile_picker.setCurrentText(current)
        self.profile_picker.blockSignals(False)

        has_any = bool(names)
        self.empty_note.setVisible(not has_any)
        for widget in (self.table, self.pronouns, self.glossary,
                       self.btn_save, self.btn_delete):
            widget.setEnabled(has_any)

        if has_any:
            self._load(self.profile_picker.currentText())
        else:
            self._profile = None
            self.table.setRowCount(0)

    def _mark_dirty(self, *_args) -> None:
        if not self._loading:
            self._dirty = True

    def _on_profile_changed(self, name: str) -> None:
        """Đổi series — HỎI trước nếu đang có sửa đổi chưa lưu.

        Bug tự soi ra được khi rà lại V62: bản đầu đổi series là nạp đè luôn,
        mọi thứ vừa gõ biến mất không một lời nào. Mất dữ liệu âm thầm là
        kiểu tệ nhất — người dùng chỉ phát hiện khi mở lại và thấy tên cũ.
        """
        if not name:
            return
        if self._dirty and self._profile is not None:
            confirmed, _ = ConfirmDialog.ask(
                self, "Bỏ thay đổi chưa lưu?",
                f"Bạn đã sửa hồ sơ «{self._profile.name}» nhưng chưa lưu.\n\n"
                "Chuyển sang series khác sẽ bỏ những thay đổi đó.",
                kind="warning", confirm_label="Bỏ thay đổi",
                cancel_label="Ở lại để lưu")
            if not confirmed:
                # Quay lại đúng hồ sơ đang sửa, không để combo trôi mất.
                self.profile_picker.blockSignals(True)
                self.profile_picker.setCurrentText(self._profile.name)
                self.profile_picker.blockSignals(False)
                return
        self._load(name)

    def _load(self, name: str) -> None:
        from autodub.character_profile import CharacterProfile

        self._loading = True
        self._profile = CharacterProfile.load(self._profiles_dir(), name)
        self.table.setRowCount(len(self._profile.characters))
        for row, character in enumerate(self._profile.characters):
            self.table.setItem(row, COL_NAME, QTableWidgetItem(character.name))
            self.table.setItem(row, COL_VOICE, QTableWidgetItem(character.voice))

            episodes = QTableWidgetItem(str(character.episodes))
            episodes.setFlags(episodes.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, COL_EPISODES, episodes)

            # Nói rõ nhân vật này được nhận ra bằng cách nào: embedding là
            # chính xác, chỉ có cao độ là dễ lẫn với người cùng giới. Người
            # dùng nhìn cột này là biết nhân vật nào đáng nghi.
            how = ("Giọng (chính xác)" if character.embedding
                   else "Cao độ (dễ lẫn)" if character.median_f0 > 0
                   else "Chưa có")
            item = QTableWidgetItem(how)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, COL_MATCH, item)

        self.pronouns.setPlainText(self._profile.pronouns)
        self.glossary.setPlainText(self._profile.glossary)
        self._loading = False
        self._dirty = False

    # ------------------------------------------------------------ hành động --

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if self._profile is None or row < 0 or row >= len(self._profile.characters):
            TOASTS.warn("Chọn một nhân vật trong bảng trước đã.")
            return
        character = self._profile.characters[row]
        confirmed, _ = ConfirmDialog.ask(
            self, "Xoá nhân vật?",
            f"Xoá «{character.name}» khỏi hồ sơ «{self._profile.name}»?\n\n"
            "Tập sau gặp lại người này sẽ coi như nhân vật mới và gán giọng "
            "lại từ đầu.",
            kind="warning", confirm_label="Xoá", cancel_label="Giữ lại")
        if not confirmed:
            return
        self._profile.characters.pop(row)
        self.table.removeRow(row)
        self._dirty = True

    def _save(self) -> None:
        """Ghi hồ sơ xuống đĩa, kèm kiểm tra tên trùng.

        Hai nhân vật cùng tên làm hỏng chính cơ chế khớp (`voice_for()` lấy
        cái đầu tiên, `remember()` cập nhật nhầm người) — chặn ở đây thay vì
        để hỏng âm thầm ở tập sau.
        """
        if self._profile is None:
            return

        names: list[str] = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, COL_NAME)
            name = (name_item.text().strip() if name_item else "")
            if not name:
                TOASTS.warn(f"Dòng {row + 1}: tên nhân vật không được để trống.")
                return
            names.append(name)

        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            TOASTS.warn(f"Tên nhân vật bị trùng: {', '.join(sorted(duplicates))}. "
                        "Mỗi nhân vật phải có tên riêng.")
            return

        for row, character in enumerate(self._profile.characters):
            character.name = names[row]
            voice_item = self.table.item(row, COL_VOICE)
            character.voice = voice_item.text().strip() if voice_item else ""

        self._profile.pronouns = self.pronouns.toPlainText().strip()
        self._profile.glossary = self.glossary.toPlainText().strip()

        path = self._profile.save(self._profiles_dir())
        if path:
            self._dirty = False
            TOASTS.info(f"Đã lưu hồ sơ «{self._profile.name}».")
        else:
            TOASTS.warn("Không lưu được hồ sơ (file có thể đang hỏng).")
