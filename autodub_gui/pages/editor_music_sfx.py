"""Nhạc nền + hiệu ứng âm thanh AI qua ElevenLabs — mini-spec V37,
docs/PLAN.md Phase G.

Tách khỏi editor_page.py cùng lý do editor_export.py: mỗi tệp giữ kích
thước dễ đọc. Đây là một lớp trộn: chỉ chứa hành vi, widget (MusicSfxPanel)
do trang chính dựng.
"""
from __future__ import annotations

from autodub.media import emphasis_points
from autodub_gui.dub_constants import friendly_error
from autodub_gui.system_open import open_file
from autodub_gui.ui.modal import ConfirmDialog
from autodub_gui.ui.toast import TOASTS


class MusicSfxMixin:
    """Sinh nhạc nền/hiệu ứng âm thanh AI (ElevenLabs, qua SaaS) và áp vào
    dự án đang mở. Luôn nghe thử trước khi áp dụng (Constraint 5, V37)."""

    def _busy_music_sfx(self) -> bool:
        if (getattr(self, "_music_sfx_worker", None) is not None
                and self._music_sfx_worker.isRunning()):
            TOASTS.warn("Đang xử lý nhạc/hiệu ứng âm thanh, hãy đợi xong đã.")
            return True
        return False

    def _show_music_sfx_error(self, title: str, advice: str,
                              message: str) -> None:
        friendly = friendly_error(message)
        if friendly is not None:
            title, advice = friendly
        ConfirmDialog.show_error(self, title, advice, detail=message)

    # -- Nhạc nền --------------------------------------------------------
    def _on_music_suggest_requested(self) -> None:
        """Đề xuất mô tả nhạc từ chính lời thoại của video (V88, V89).

        Có tài khoản thì hỏi trợ lý ở máy chủ (đọc hiểu nội dung thật, 2 Vox);
        không thì đo trên máy bằng luật — tức thì, 0 Vox. Chạy trong luồng
        riêng vì đường máy chủ mất vài giây.
        """
        if getattr(self, "_music_suggest_worker", None) is not None \
                and self._music_suggest_worker.isRunning():
            return
        from autodub_gui.workers import MusicSuggestWorker

        segments = getattr(self, "_segments", None) or []
        text_field = ""
        state = getattr(self, "_state", None)
        if state is not None and getattr(state, "target", None) is not None:
            text_field = getattr(state.target, "text_field", "") or ""
        tieu_de = ""
        if state is not None:
            tieu_de = str(getattr(state, "title", "") or "")

        self.music_sfx_panel.set_music_status("Đang xem nội dung video…")
        worker = MusicSuggestWorker(segments, text_field, tieu_de, parent=self)
        worker.finished_ok.connect(self._on_music_suggest_done)
        self._music_suggest_worker = worker
        worker.start()

    def _on_music_suggest_done(self, goi_y: list, nguon: str) -> None:
        self.music_sfx_panel.show_music_suggestions(goi_y, nguon=nguon)

    def _on_music_requested(self, description: str) -> None:
        if self._busy_warn() or self._busy_music_sfx():
            return
        if not description:
            self.music_sfx_panel.set_music_status(
                "Hãy mô tả tâm trạng nhạc nền trước.")
            return
        from autodub_gui.workers import MusicSfxWorker

        worker = MusicSfxWorker("music", self._work_dir,
                                description=description, parent=self)
        worker.finished_ok.connect(self._on_music_done)
        worker.failed.connect(self._on_music_failed)
        self.music_sfx_panel.set_music_status("Đang sinh nhạc nền…")
        self._music_sfx_worker = worker
        worker.start()

    def _on_music_done(self, path: str, billing: dict) -> None:
        charged = billing.get("creditCharged", 0)
        self.music_sfx_panel.set_music_status(
            f"Đã sinh xong (tốn {charged} Vox). Nghe thử trước khi dùng.",
            path=path)

    def _on_music_failed(self, message: str) -> None:
        self.music_sfx_panel.set_music_status("")
        self._show_music_sfx_error(
            "Không sinh được nhạc nền",
            "Có lỗi khi gọi máy chủ sinh nhạc. Thử lại sau.", message)

    def _on_apply_music(self) -> None:
        """"Dùng nhạc này": ghim bg_mode="ai_music" vào tùy chọn dự án —
        lượt Xuất video tiếp theo sẽ dùng data/ai_music.wav vừa sinh (xem
        editor.resolve_existing_background())."""
        self.background_panel.mode.set_key("ai_music")
        self._save_render_opts()
        TOASTS.success(
            "Đã chọn Nhạc nền AI — bấm Xuất video để ghép vào phim.")

    # -- Hiệu ứng âm thanh -------------------------------------------------
    def _on_sfx_points_requested(self) -> None:
        self._flush_edits()
        text_field = self._state.target.text_field if self._state else "text"
        points = emphasis_points.detect_emphasis_points(
            self._segments, text_field)
        self.music_sfx_panel.set_emphasis_points(points)

    def _on_sfx_requested(self, timestamp: float, description: str,
                          name: str) -> None:
        if self._busy_warn() or self._busy_music_sfx():
            return
        from autodub_gui.workers import MusicSfxWorker

        worker = MusicSfxWorker("sfx_preview", self._work_dir,
                                description=description, name=name, parent=self)
        worker.finished_ok.connect(
            lambda path, billing: self._on_sfx_preview_done(
                path, billing, timestamp))
        worker.failed.connect(self._on_sfx_failed)
        self.music_sfx_panel.set_sfx_status("Đang sinh hiệu ứng âm thanh…")
        self._music_sfx_worker = worker
        worker.start()

    def _on_sfx_preview_done(self, path: str, billing: dict,
                             timestamp: float) -> None:
        charged = billing.get("creditCharged", 0)
        self.music_sfx_panel.set_sfx_status(
            f"Đã sinh xong (tốn {charged} Vox). Nghe thử trước khi chèn.",
            path=path, timestamp=timestamp)

    def _on_sfx_apply_requested(self, timestamp: float, sfx_path: str) -> None:
        if self._busy_warn() or self._busy_music_sfx():
            return
        from autodub_gui.workers import MusicSfxWorker

        worker = MusicSfxWorker("sfx_apply", self._work_dir,
                                timestamp_s=timestamp, sfx_wav_path=sfx_path,
                                parent=self)
        worker.finished_ok.connect(self._on_sfx_apply_done)
        worker.failed.connect(self._on_sfx_failed)
        self.music_sfx_panel.set_sfx_status("Đang chèn hiệu ứng vào video…")
        # Chèn sẽ ghi đè dubbed_video.mp4 — nhả video trước, cùng lý do
        # release_video() trong _start_resynth/_export (WinError 32).
        self._sfx_apply_resume_pos = self.release_video()
        self._music_sfx_worker = worker
        worker.start()

    def _on_sfx_apply_done(self, path: str, _billing: dict) -> None:
        self.music_sfx_panel.set_sfx_status("Đã chèn hiệu ứng vào video.")
        self._reload_player(path)
        self.restore_video(getattr(self, "_sfx_apply_resume_pos", None))
        self._sfx_apply_resume_pos = None
        TOASTS.success("Đã chèn hiệu ứng âm thanh vào video.",
                       action_label="Mở video",
                       on_action=lambda: open_file(path))

    def _on_sfx_failed(self, message: str) -> None:
        self.music_sfx_panel.set_sfx_status("")
        self.restore_video(getattr(self, "_sfx_apply_resume_pos", None))
        self._sfx_apply_resume_pos = None
        self._show_music_sfx_error(
            "Không xử lý được hiệu ứng âm thanh",
            "Có lỗi khi gọi máy chủ. Thử lại sau.", message)
