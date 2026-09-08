"""Hộp thoại "Mở video + phụ đề nước ngoài (tự dịch)..." (08/09/2026).

Nối hai tính năng đã có, theo đúng yêu cầu người dùng: *"định hướng nó luồng
tự động nối luôn Nhập phụ đề với Dịch phụ đề thành một luồng — phụ đề nước
ngoài + video → tự dịch → dự án lồng tiếng luôn"*. Trước đây người có phụ đề
tiếng nước ngoài phải tự làm 2 bước tách rời: trang Dịch phụ đề rời (dịch ra
file `.srt` mới) rồi trang này (nút "Mở video + phụ đề tiếng Việt...", chỉ
nhận phụ đề ĐÃ tiếng Việt) — ghi rõ ở `nhap_phu_de.py` từ 26/8/2026 là
"chặng sau", chưa ai quay lại làm.

Khác nút "Mở video + phụ đề tiếng Việt..." (chạy thẳng trên luồng giao diện
vì chỉ đọc 1 tệp văn bản, không mạng không engine nặng — luật C7), hộp thoại
này LUÔN chạy qua `NhapPhuDeDichWorker` (QThread) vì bước dịch (SaaS qua
mạng, hoặc nạp model NLLB 600MB offline) có thể mất hàng chục giây.

Ngôn ngữ phụ đề nguồn dùng lại đúng ô chọn FLORES-200 có thể gõ tìm của
trang Dịch phụ đề rời (`autodub_gui/ui/flores_picker.py`) — phụ đề nhập vào
có thể ở BẤT KỲ ngôn ngữ nào, không giới hạn theo `SOURCE_LANG_MAP` hẹp của
pipeline dub. Ngôn ngữ đích dùng `consts.DUB_TARGETS` (10 ngôn ngữ đã đăng
ký giọng đọc) — đúng ô đã dùng ở trang Tạo dự án, không dựng nhãn mới.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout,
    QWidget,
)

from autodub_gui import dub_constants as consts
from autodub_gui import tokens
from autodub_gui.log_text import error_line
from autodub_gui.ui.buttons import GhostButton, PrimaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.flores_picker import language_options, make_searchable
from autodub_gui.ui.inputs import FilePicker, LabeledCombo
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import NhapPhuDeDichWorker

_DEFAULT_SOURCE = "eng_Latn"


class NhapPhuDeDichDialog(QDialog):
    """Chọn video + phụ đề nước ngoài + ngôn ngữ đích + cách dịch, rồi dựng
    thẳng một dự án lồng tiếng đã dịch sẵn."""

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: NhapPhuDeDichWorker | None = None
        self.thu_muc_ket_qua: str | None = None   # đọc sau khi accept()

        self.setWindowTitle("Mở video + phụ đề nước ngoài (tự dịch)")
        self.setModal(True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(tokens.SP_5, tokens.SP_5,
                                tokens.SP_5, tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        hint = QLabel(
            "Chọn một video và một tệp phụ đề .srt/.vtt ở NGÔN NGỮ NƯỚC "
            "NGOÀI. App tự dịch sang ngôn ngữ đích rồi dựng thành dự án để "
            "bạn chọn giọng đọc và xuất video — không cần dịch riêng bằng "
            "trang «Dịch phụ đề» trước.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FS_LABEL}px;")
        root.addWidget(hint)
        root.addWidget(self._build_input_card())

        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(
            f"color: {tokens.WARNING}; font-size: {tokens.FS_META}px; "
            f"background: transparent;")
        self.warning.hide()
        root.addWidget(self.warning)

        self.log = LogPanel()
        self.log.setMaximumHeight(120)
        root.addWidget(self.log)

        root.addLayout(self._build_actions())
        self._refresh_warning()

    # -- Dựng giao diện ------------------------------------------------
    def _build_input_card(self) -> QWidget:
        card = Card(padding=tokens.SP_4)

        self.video = FilePicker(
            "Video", "video.mp4",
            "Video gốc, còn ở ngôn ngữ nước ngoài.",
            name_filter="Video (*.mp4 *.mov *.mkv *.avi *.webm)")
        card.body.addWidget(self.video)

        self.phu_de = FilePicker(
            "Tệp phụ đề", "phim.srt",
            "Phụ đề .srt/.vtt ở CÙNG ngôn ngữ với video — chưa dịch.",
            name_filter="Phụ đề (*.srt *.vtt)")
        card.body.addWidget(self.phu_de)

        langs = QHBoxLayout()
        langs.setSpacing(tokens.SP_3)
        self.source = LabeledCombo(
            "Ngôn ngữ phụ đề", language_options(),
            "Ngôn ngữ hiện có trong tệp phụ đề bạn chọn.")
        self._select_key(self.source, _DEFAULT_SOURCE)
        make_searchable(self.source)
        self.target = LabeledCombo(
            "Ngôn ngữ đích", consts.DUB_TARGETS,
            "Ngôn ngữ muốn lồng tiếng sang.")
        self.source.changed.connect(self._refresh_warning)
        self.target.changed.connect(self._refresh_warning)
        langs.addWidget(self.source, 1)
        langs.addWidget(self.target, 1)
        card.body.addLayout(langs)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(tokens.SP_3)
        mode_label = QLabel("Dịch bằng:")
        mode_label.setStyleSheet(
            f"color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FS_LABEL}px; "
            f"background: transparent;")
        self.mode_group = QButtonGroup(self)
        self.mode_local = QRadioButton(
            "Máy này (offline, miễn phí, chất lượng thấp hơn)")
        self.mode_saas = QRadioButton(
            "Máy chủ VoxDub (tốn Vox, chất lượng cao hơn)")
        self.mode_local.setChecked(True)
        self.mode_group.addButton(self.mode_local)
        self.mode_group.addButton(self.mode_saas)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_local)
        mode_row.addWidget(self.mode_saas)
        mode_row.addStretch()
        card.body.addLayout(mode_row)

        from autodub.saas_client import is_configured

        configured = is_configured()
        self.mode_saas.setEnabled(configured)
        if not configured:
            self.mode_saas.setToolTip(
                "Chưa cấu hình máy chủ VoxDub (VOXDUB_API_URL) — chỉ dịch "
                "được bằng máy này.")
        return card

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(tokens.SP_2)
        row.addStretch()
        self.btn_cancel = GhostButton("Huỷ")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_start = PrimaryButton("Dịch và tạo dự án")
        self.btn_start.clicked.connect(self._start)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_start)
        return row

    # -- Trạng thái ------------------------------------------------------
    def _select_key(self, combo: LabeledCombo, key: str) -> None:
        idx = combo.combo.findData(key)
        if idx >= 0:
            combo.combo.setCurrentIndex(idx)

    def _target_flores(self) -> str | None:
        from autodub.languages import get_target
        from autodub.text.translate_local import flores_code

        return flores_code(get_target(self.target.current_key()).code)

    def _refresh_warning(self) -> None:
        from autodub.text.flores200 import VERIFIED_QUALITY_CODES

        target_flores = self._target_flores()
        codes = {self.source.current_key()} | ({target_flores} if target_flores else set())
        if codes - VERIFIED_QUALITY_CODES:
            self.warning.setText(
                "Lưu ý: chất lượng dịch cho ngôn ngữ bạn chọn CHƯA được "
                "kiểm chứng thật (chỉ tiếng Việt/tiếng Anh đã live-verify) "
                "— kết quả có thể kém hơn kỳ vọng.")
            self.warning.show()
        else:
            self.warning.hide()

    def _set_running(self, running: bool) -> None:
        self.btn_start.set_loading(running, "Đang dịch…")
        self.btn_cancel.setEnabled(not running)
        self.video.setEnabled(not running)
        self.phu_de.setEnabled(not running)
        self.source.setEnabled(not running)
        self.target.setEnabled(not running)
        self.mode_local.setEnabled(not running)
        self.mode_saas.setEnabled(not running and self.mode_saas.toolTip() == "")

    # -- Chạy ------------------------------------------------------------
    def _start(self) -> None:
        if self.is_running():
            return
        video = self.video.text().strip()
        phu_de = self.phu_de.text().strip()
        if not video or not os.path.isfile(video):
            TOASTS.warn("Chọn một tệp video hợp lệ trước.")
            return
        if not phu_de or not os.path.isfile(phu_de):
            TOASTS.warn("Chọn một tệp phụ đề .srt/.vtt hợp lệ trước.")
            return
        source_flores = self.source.current_key()
        target_key = self.target.current_key()
        if not source_flores or not target_key:
            TOASTS.warn("Chọn ngôn ngữ phụ đề và ngôn ngữ đích trước.")
            return
        mode = "saas" if self.mode_saas.isChecked() else "local"

        settings = self._settings_provider()
        goc = os.path.join(str(getattr(settings, "output_dir", "") or "."), "VN")

        self.log.reset_log()
        self._set_running(True)

        worker = NhapPhuDeDichWorker(
            video, phu_de, goc, source_flores, target_key, mode, settings, self)
        worker.log.connect(self.log.append_log)
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._set_running(False))
        self._worker = worker
        worker.start()

    def _on_finished(self, ket) -> None:
        for dong in ket.canh_bao:
            TOASTS.warn(dong)
        msg = f"Đã dịch và nhập {ket.so_cau} câu."
        if ket.credit_charged:
            msg += f" Đã trừ {ket.credit_charged} Vox."
        TOASTS.success(msg)
        self.thu_muc_ket_qua = ket.thu_muc
        self.accept()

    #: Câu khuyên khi KHÔNG đoán được nguyên nhân — giống trang Dịch phụ đề.
    _KHUYEN_CHUNG = ("Kiểm tra lại tệp phụ đề, ngôn ngữ đã chọn, hoặc kết "
                     "nối mạng (nếu đang dịch qua máy chủ VoxDub), rồi thử "
                     "lại.")

    def _on_failed(self, message: str) -> None:
        text, level = error_line(message)
        self.log.append_log(text, level)
        than = self._KHUYEN_CHUNG
        if text.startswith("Dừng lại: "):
            than = text[len("Dừng lại: "):]
        ConfirmDialog.show_error(self, "Không nhập được", than, detail=message)

    # -- Vòng đời ------------------------------------------------------
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def reject(self) -> None:
        if self.is_running():
            # Chưa có cơ chế huỷ giữa chừng (cùng giới hạn với trang Dịch
            # phụ đề rời, V14) — không cho đóng dở dang vì lượt dịch/dựng
            # dự án đang ghi tệp, đóng ngang sẽ để lại thư mục dự án nửa vời.
            TOASTS.warn("Đang dịch — chờ xong rồi hẵng đóng.")
            return
        super().reject()
