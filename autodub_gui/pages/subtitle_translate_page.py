"""Trang Dịch phụ đề rời — mini-spec V14 (docs/PLAN.md).

Dịch 1 file `.srt`/`.vtt` ĐỘC LẬP, không cần dự án lồng tiếng nào đang mở.
Ngôn ngữ nhận vào là mã FLORES-200 (`autodub/text/flores200.py`), KHÔNG phải
`TargetLang` của pipeline dub — xem Constraint 1 của V14, docs/PLAN.md.

CHƯA verify được bằng cách bấm chuột thật (môi trường viết code này không có
PySide6/display) — xem docs/TEST_LOG.md mục V14, Remaining Limits.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCompleter, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout,
    QWidget,
)

from autodub_gui import tokens
from autodub_gui.log_text import error_line
from autodub_gui.pages import BasePage
from autodub_gui.run_state import REGISTRY, ActiveJob
from autodub_gui.system_open import open_folder
from autodub_gui.ui.buttons import GhostButton, PrimaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.inputs import FilePicker, LabeledCombo
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import SubtitleTranslateWorker

_PAGE_MARGIN = 28
_DEFAULT_SOURCE = "eng_Latn"
_DEFAULT_TARGET = "vie_Latn"


def _language_options() -> list[tuple[str, str]]:
    from autodub.text.flores200 import FLORES200_LANGUAGES

    return sorted(((name, code) for code, name in FLORES200_LANGUAGES.items()),
                  key=lambda pair: pair[0])


def _make_searchable(combo: LabeledCombo) -> None:
    """Cho gõ để lọc trong ~200 mục — QComboBox editable + QCompleter (mẫu
    Qt chuẩn), không đổi cách chọn bằng chuột hay `current_key()`."""
    box = combo.combo
    box.setEditable(True)
    box.setInsertPolicy(box.InsertPolicy.NoInsert)
    completer = QCompleter(box.model(), box)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    box.setCompleter(completer)


class SubtitleTranslatePage(BasePage):
    """Dịch 1 file phụ đề `.srt`/`.vtt` sang ngôn ngữ khác, độc lập dự án."""

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: SubtitleTranslateWorker | None = None
        self._last_output_dir: str | None = None
        self._build()
        self._refresh_warning()

    # -- Dựng giao diện ------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2,
                                _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)
        root.addWidget(self._build_input_card())
        root.addLayout(self._build_actions())

        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(
            f"color: {tokens.WARNING}; font-size: {tokens.FS_META}px; "
            f"background: transparent;")
        self.warning.hide()
        root.addWidget(self.warning)

        self.log = LogPanel()
        self.log.setMaximumHeight(140)
        root.addWidget(self.log)
        root.addStretch()

    def _build_input_card(self) -> QWidget:
        card = Card(padding=tokens.SP_4)
        card.add_header("File phụ đề")

        self.input_file = FilePicker(
            "File cần dịch", "phim.srt",
            "Chọn file .srt hoặc .vtt — bản dịch được lưu ra file MỚI, "
            "không ghi đè file gốc.",
            name_filter="Phụ đề (*.srt *.vtt)")
        card.body.addWidget(self.input_file)

        langs = QHBoxLayout()
        langs.setSpacing(tokens.SP_3)
        options = _language_options()
        self.source = LabeledCombo("Ngôn ngữ nguồn", options,
                                   "Ngôn ngữ hiện có trong file phụ đề.")
        self.target = LabeledCombo("Ngôn ngữ đích", options,
                                   "Ngôn ngữ muốn dịch sang.")
        self._select_key(self.source, _DEFAULT_SOURCE)
        self._select_key(self.target, _DEFAULT_TARGET)
        _make_searchable(self.source)
        _make_searchable(self.target)
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
        return card

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(tokens.SP_2)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            f"color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FS_LABEL}px; "
            f"background: transparent;")
        row.addWidget(self.summary, 1)
        self.btn_open = GhostButton("Mở thư mục chứa file")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_output_folder)
        self.btn_start = PrimaryButton("Dịch")
        self.btn_start.clicked.connect(self._start)
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_start)
        return row

    # -- Trạng thái ------------------------------------------------------
    def on_shown(self) -> None:
        """Chạy mỗi lần vào trang — Constraint 5 của V14: KHÔNG ẩn tuỳ chọn
        local dù có server cấu hình; chỉ khoá tuỳ chọn SaaS khi CHƯA cấu
        hình (chưa `is_configured()`), không ẩn cả trang."""
        from autodub.saas_client import is_configured

        configured = is_configured()
        self.mode_saas.setEnabled(configured)
        if not configured:
            self.mode_saas.setToolTip(
                "Chưa cấu hình máy chủ VoxDub (VOXDUB_API_URL) — chỉ dịch "
                "được bằng máy này.")
            if self.mode_saas.isChecked():
                self.mode_local.setChecked(True)
        else:
            self.mode_saas.setToolTip("")

    def _select_key(self, combo: LabeledCombo, key: str) -> None:
        idx = combo.combo.findData(key)
        if idx >= 0:
            combo.combo.setCurrentIndex(idx)

    def _refresh_warning(self) -> None:
        from autodub.text.flores200 import VERIFIED_QUALITY_CODES

        codes = {self.source.current_key(), self.target.current_key()}
        if codes - VERIFIED_QUALITY_CODES:
            self.warning.setText(
                "Lưu ý: chất lượng dịch cho ngôn ngữ bạn chọn CHƯA được "
                "kiểm chứng thật (chỉ tiếng Việt/tiếng Anh đã live-verify) "
                "— kết quả có thể kém hơn kỳ vọng.")
            self.warning.show()
        else:
            self.warning.hide()

    # -- Chạy ------------------------------------------------------------
    def _start(self) -> None:
        if self.is_running():
            return
        path = self.input_file.text()
        if not path or not os.path.isfile(path):
            TOASTS.warn("Chọn một file .srt/.vtt hợp lệ trước.")
            return
        source_key = self.source.current_key()
        target_key = self.target.current_key()
        if not source_key or not target_key:
            TOASTS.warn("Chọn ngôn ngữ nguồn và đích trước.")
            return
        if source_key == target_key:
            TOASTS.warn("Ngôn ngữ nguồn và đích đang giống nhau.")
            return
        mode = "saas" if self.mode_saas.isChecked() else "local"

        self.log.reset_log()
        self.btn_open.setEnabled(False)
        self.summary.setText("")
        self._set_running(True)

        worker = SubtitleTranslateWorker(
            path, source_key, target_key, mode, self._settings_provider(), self)
        worker.log.connect(self.log.append_log)
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._set_running(False))
        self._worker = worker
        REGISTRY.start_job(
            ActiveJob(kind="subtitle_translate", title="Dịch phụ đề",
                      work_dir=os.path.dirname(os.path.abspath(path))))
        worker.start()

    def _set_running(self, running: bool) -> None:
        self.btn_start.set_loading(running, "Đang dịch")
        self.input_file.setEnabled(not running)
        self.mode_local.setEnabled(not running)
        self.mode_saas.setEnabled(not running and self.mode_saas.toolTip() == "")

    def _on_finished(self, result) -> None:
        REGISTRY.finish_job(True, f"Dịch xong {result.cue_count} dòng")
        self._last_output_dir = os.path.dirname(os.path.abspath(result.output_path))
        self.btn_open.setEnabled(True)

        msg = (f"Đã dịch {result.cue_count} dòng -> "
               f"{os.path.basename(result.output_path)}")
        if result.skipped_block_count:
            msg += f" (bỏ qua {result.skipped_block_count} khối hỏng ở file gốc)"
        if result.credit_charged:
            msg += f" — đã trừ {result.credit_charged} Vox."
        self.summary.setText(msg)
        TOASTS.success("Dịch phụ đề xong.", action_label="Mở thư mục",
                       on_action=self._open_output_folder)

    #: Câu khuyên khi KHÔNG đoán được nguyên nhân — cố ý liệt kê vài hướng.
    _KHUYEN_CHUNG = ("Kiểm tra lại file phụ đề, ngôn ngữ đã chọn, hoặc kết nối "
                     "mạng (nếu đang dịch qua máy chủ VoxDub), rồi thử lại.")

    def _on_failed(self, message: str) -> None:
        text, level = error_line(message)
        self.log.append_log(text, level)
        REGISTRY.finish_job(False, message[:120])
        # C61: khi lời báo đã nói được VIỆC CẦN LÀM (vd "chưa cài bộ dịch ngoại
        # tuyến — chạy bộ cài này"), thay nó bằng câu khuyên chung chung là lấy
        # đi đúng thứ người dùng cần. Câu chung chỉ dành cho ca thật sự không
        # đoán được nguyên nhân.
        than = self._KHUYEN_CHUNG
        if text.startswith("Dừng lại: "):
            than = text[len("Dừng lại: "):]
        ConfirmDialog.show_error(self, "Không dịch được", than, detail=message)

    def _open_output_folder(self) -> None:
        if self._last_output_dir:
            open_folder(self._last_output_dir)

    # -- Vòng đời ------------------------------------------------------
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def shutdown(self) -> None:
        # Không có cơ chế huỷ giữa chừng (V14 chưa làm — lượt dịch 1 file
        # thường nhanh, chưa đáng cơ chế huỷ như DownloadWorker). Chỉ chờ
        # cho xong thay vì bỏ dở dữ liệu đang ghi.
        if self.is_running():
            self._worker.wait(5000)
