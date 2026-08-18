"""Trang Chép lời — chuyển giọng nói thành văn bản (mini-spec V71).

Nhận LIÊN KẾT (YouTube/Facebook/TikTok/Douyin…), file video, hoặc file âm
thanh; trả về văn bản kèm mốc thời gian.

Tách hẳn khỏi luồng dub vì dừng ở chỗ khác: dub luôn chạy tiếp sang dịch +
lồng tiếng + ghép video, còn ai chỉ cần bản chữ thì mọi bước sau ASR đều là
thời gian bỏ đi.

Chỉ MỘT ô nhập cho cả liên kết lẫn đường dẫn file — người dùng dán cái gì thì
dán, `transcribe_tool.is_url()` tự phân đường. Bắt họ chọn trước "tôi sắp dán
liên kết hay chọn file" là bắt họ trả lời một câu hỏi máy tự trả lời được.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from autodub_gui import tokens
from autodub_gui.pages import BasePage
from autodub_gui.system_open import open_folder
from autodub_gui.ui.buttons import GhostButton, PrimaryButton, SecondaryButton
from autodub_gui.ui.cards import Card
from autodub_gui.ui.inputs import LabeledCombo, LabeledLineEdit
from autodub_gui.ui.toast import TOASTS
from autodub_gui.widgets import LogPanel
from autodub_gui.workers import TranscribeWorker

_PAGE_MARGIN = 28

#: `LabeledCombo` nhận `(NHÃN, khoá)` — nhãn trước, khoá sau.
#: Viết ngược thì combo hiện ra khoá và `current_key()` trả về nhãn;
#: smoke test dựng trang bắt được đúng lỗi này.
#:
#: Ngôn ngữ nguồn hay dùng. "" = theo cài đặt chung, để người dùng không phải
#: chọn lại thứ họ đã đặt một lần trong Cài đặt.
_LANGS = [
    ("Theo cài đặt chung", ""),
    ("Tiếng Việt", "vi"),
    ("Tiếng Anh", "en"),
    ("Tiếng Trung", "zh"),
    ("Tiếng Hàn", "ko"),
    ("Tiếng Nhật", "ja"),
    ("Tiếng Thái", "th"),
    ("Tiếng Indonesia", "id"),
]

_FORMATS = [
    ("Văn bản + phụ đề (.txt + .srt)", "txt,srt"),
    ("Chỉ văn bản (.txt)", "txt"),
    ("Chỉ phụ đề (.srt)", "srt"),
    ("Phụ đề web (.vtt)", "vtt"),
    ("Tất cả định dạng", "txt,srt,vtt,json"),
]

_MEDIA_FILTER = ("Video hoặc âm thanh (*.mp4 *.mkv *.mov *.avi *.webm "
                 "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus);;Tất cả (*.*)")


class TranscribePage(BasePage):
    """Chép lời một liên kết hoặc file thành văn bản."""

    def __init__(self, settings_provider, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self._worker: TranscribeWorker | None = None
        self._last_output_dir: str = ""
        self._build()

    # ------------------------------------------------------------ dựng UI --
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAGE_MARGIN, tokens.SP_2, _PAGE_MARGIN, tokens.SP_5)
        root.setSpacing(tokens.SP_4)

        card = Card(padding=tokens.SP_4)
        card.add_header("Chép lời")

        self.source = LabeledLineEdit(
            "Liên kết hoặc file", "https://… hoặc D:\\video\\bai-giang.mp4",
            "Dán liên kết video, hoặc bấm «Chọn file…» để lấy file trên máy "
            "(video lẫn mp3 đều được).")
        card.body.addWidget(self.source)

        chon = QHBoxLayout()
        chon.setSpacing(tokens.SP_2)
        self.btn_pick = SecondaryButton("Chọn file…")
        self.btn_pick.clicked.connect(self._pick_file)
        chon.addWidget(self.btn_pick)
        chon.addStretch()
        card.body.addLayout(chon)

        hang = QHBoxLayout()
        hang.setSpacing(tokens.SP_3)
        self.language = LabeledCombo(
            "Ngôn ngữ đang nói", _LANGS,
            "Chọn đúng ngôn ngữ trong video thì chép lời chính xác hơn hẳn.")
        self.formats = LabeledCombo(
            "Xuất ra", _FORMATS,
            ".txt để đọc và soạn lại, .srt/.vtt để gắn vào video.")
        hang.addWidget(self.language, 1)
        hang.addWidget(self.formats, 1)
        card.body.addLayout(hang)

        self.output_dir = LabeledLineEdit(
            "Thư mục lưu kết quả", "",
            "Để trống thì lưu cùng chỗ với các dự án lồng tiếng.")
        card.body.addWidget(self.output_dir)
        root.addWidget(card)

        hanh_dong = QHBoxLayout()
        hanh_dong.setSpacing(tokens.SP_3)
        self.btn_run = PrimaryButton("Bắt đầu chép lời")
        self.btn_run.clicked.connect(self._run)
        hanh_dong.addWidget(self.btn_run)
        self.btn_stop = SecondaryButton("Dừng")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        hanh_dong.addWidget(self.btn_stop)
        self.btn_open = GhostButton("Mở thư mục kết quả")
        self.btn_open.clicked.connect(self._open_output)
        self.btn_open.setEnabled(False)
        hanh_dong.addWidget(self.btn_open)
        hanh_dong.addStretch()
        root.addLayout(hanh_dong)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        self.log = LogPanel()
        self.log.setMaximumHeight(160)
        root.addWidget(self.log)
        root.addStretch()

    # ----------------------------------------------------------- hành động --
    def _pick_file(self) -> None:
        """Chọn NHIỀU file một lượt — mini-spec V72.

        Nhiều file nối bằng dấu `|` vì đường dẫn Windows chứa cả dấu phẩy lẫn
        dấu chấm phẩy, còn `|` là ký tự Windows CẤM đặt tên file nên không bao
        giờ đụng độ.
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video hoặc file âm thanh (chọn được nhiều)", "",
            _MEDIA_FILTER)
        if paths:
            self.source.set_text(" | ".join(paths))

    def _sources(self) -> list[str]:
        """Tách ô nhập thành danh sách nguồn — mini-spec V72."""
        return [p.strip() for p in self.source.text().split("|") if p.strip()]

    def _resolve_output_dir(self) -> str:
        thu_muc = self.source_output_dir()
        if thu_muc:
            return thu_muc
        settings = self._settings_provider()
        return os.path.join(str(getattr(settings, "output_dir", "") or "."),
                            "chep_loi")

    def source_output_dir(self) -> str:
        return self.output_dir.text()

    def _run(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            TOASTS.warn("Đang chép lời — chờ lượt này xong đã.")
            return

        sources = self._sources()
        if not sources:
            TOASTS.warn("Dán liên kết hoặc chọn file trước đã.")
            return
        # File trên máy: kiểm TỒN TẠI ngay, đừng để người dùng chờ hết bước
        # chuẩn bị rồi mới báo gõ sai đường dẫn. Thư mục cũng hợp lệ (chép lời
        # cả thư mục), nên chỉ chặn thứ không phải liên kết, không phải file,
        # cũng không phải thư mục.
        from autodub.transcribe_tool import is_url
        thieu = [s for s in sources
                 if not is_url(s) and not os.path.isfile(s) and not os.path.isdir(s)]
        if thieu:
            TOASTS.warn(f"Không tìm thấy: {thieu[0]}")
            return

        output_dir = self._resolve_output_dir()
        formats = tuple(f for f in str(self.formats.current_key()).split(",") if f)

        self.log.setPlainText("")
        self.status.setText("Đang chuẩn bị…")
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._last_output_dir = output_dir

        worker = TranscribeWorker(
            sources, output_dir, self._settings_provider(),
            language=str(self.language.current_key() or ""),
            formats=formats, with_timestamps=True, parent=self)
        worker.log.connect(self.log.append_log)
        worker.progress.connect(self._on_progress)
        worker.item_status.connect(self._on_item)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.btn_stop.setEnabled(False)
            # Nói rõ là "đang dừng" chứ không phải "đã dừng": mục đang chạy
            # còn chạy nốt câu hiện tại rồi mới thoát.
            self.status.setText("Đang dừng…")

    def _on_progress(self, step: str, detail: str) -> None:
        self.status.setText(detail or step)

    def _on_item(self, i: int, tong: int, source: str, status: str,
                 detail: str = "") -> None:
        nhan = {"xong": "xong", "hong": "HỎNG", "huy": "đã huỷ"}.get(status, status)
        dong = f"[{i + 1}/{tong}] {nhan}: {source}"
        # Lý do phải đi kèm ngay dòng hỏng. Bộ lọc Nhật ký của lõi
        # (`log_text.notice_for`) bỏ mọi thông báo lạ có đường dẫn/URL, nên
        # cảnh báo "Chép lời hỏng «…»: …" của `transcribe_many` KHÔNG bao giờ
        # lên tới đây — dòng này là chỗ duy nhất người dùng thấy được lý do.
        if status == "hong" and detail:
            dong += f" — {detail}"
        self.log.append_log(dong, 40 if status == "hong" else 20)

    def _on_done(self, items) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_open.setEnabled(True)
        xong = [m for m in items if m.status == "xong"]
        hong = [m for m in items if m.status == "hong"]
        huy = [m for m in items if m.status == "huy"]
        so_cau = sum(len(m.result.segments) for m in xong if m.result)

        if len(items) == 1 and xong:
            self.status.setText(f"Xong {so_cau} câu — đã lưu: "
                                + ", ".join(sorted(xong[0].result.outputs)))
        else:
            phan = [f"Xong {len(xong)}"]
            if hong:
                phan.append(f"hỏng {len(hong)}")
            if huy:
                phan.append(f"đã huỷ {len(huy)}")
            self.status.setText(" · ".join(phan) + f" — tổng {so_cau} câu")
        # Hỏng lẻ tẻ vẫn phải nói ra: báo "xong" trong khi 3/5 mục hỏng là nói dối.
        if hong:
            TOASTS.warn(f"{len(hong)} mục không chép lời được — xem nhật ký.")
        elif huy:
            TOASTS.info(f"Đã dừng. Giữ nguyên {len(xong)} mục đã xong.")
        else:
            TOASTS.info(f"Chép lời xong: {so_cau} câu.")

    def _on_failed(self, message: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        # Nói nguyên văn lỗi thật chứ không nuốt thành "có lỗi xảy ra" —
        # người dùng cần biết là sai đường dẫn, mất mạng, hay video có khoá.
        self.status.setText(f"Không chép lời được: {message}")
        self.log.append_log(message, 40)
        TOASTS.warn("Chép lời thất bại — xem chi tiết bên dưới.")

    def _open_output(self) -> None:
        if self._last_output_dir and os.path.isdir(self._last_output_dir):
            open_folder(self._last_output_dir)
        else:
            TOASTS.warn("Chưa có thư mục kết quả nào.")
