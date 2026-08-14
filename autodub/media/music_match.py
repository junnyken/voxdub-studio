"""Nhạc nền + hiệu ứng âm thanh AI qua ElevenLabs — mini-spec V37,
docs/PLAN.md Phase G.

Orchestration: gọi SaaS (`autodub.saas_client`) để sinh nhạc/SFX THẬT, lưu
vào `work_dir` theo đúng quy ước `autodub.editor.resolve_existing_
background()` đọc lại (Design Choice: tái dùng cơ chế trộn/duck nhạc nền
đã có của pipeline chính — KHÔNG viết lại logic mixing).

Nhạc nền: lưu vào `data/ai_music.wav`, dùng qua `bg_mode="ai_music"` mới
(xem `editor.resolve_existing_background()`) — LOẠI TRỪ LẪN NHAU với
`bg_mode="demucs"`/`"duck"` theo thiết kế (nhạc AI chỉ hợp lý khi KHÔNG
giữ nhạc nền gốc của video, xem Audit Before Build của mini-spec).

Hiệu ứng âm thanh: chèn vào video ĐÃ MUX (`dubbed_video.mp4`) tại 1
timestamp cụ thể qua ffmpeg overlay — KHÔNG đi qua `merge_segments()`
(hàm đó trộn 1 TRACK NỀN liên tục xuyên suốt video, SFX là 1 điểm chèn rời
rạc, khác bài toán).

Tính năng CHỈ dùng được ở chế độ SaaS (server quản lý key ElevenLabs,
Design Choice của V37) — `is_configured()` là cổng duy nhất, đúng nguyên
tắc xuyên suốt dự án (`saas_client.is_configured()`).
"""
from __future__ import annotations

import os
import subprocess

from autodub.workdir import data_path


class MusicMatchError(Exception):
    """Lỗi thật khi sinh/chèn nhạc-SFX — caller (GUI) hiển thị rõ, không
    giả vờ có kết quả."""


def is_available() -> bool:
    from autodub.saas_client import is_configured
    return is_configured()


def _mp3_to_wav(mp3_path: str, wav_path: str, sample_rate: int = 44100) -> None:
    """Chuyển MP3 (ElevenLabs trả về) thành WAV PCM16 qua ffmpeg — cùng
    định dạng các track nền khác trong work_dir
    (original_audio.wav/no_vocals.wav)."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", mp3_path,
         "-ar", str(sample_rate), "-ac", "2", "-sample_fmt", "s16", wav_path],
        capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise MusicMatchError(
            f"Không chuyển được MP3 sang WAV: {(result.stderr or '')[-500:]}")


def generate_and_save_music(
    work_dir: str, prompt: str, *, music_length_ms: int | None = None,
) -> dict:
    """Sinh 1 đoạn nhạc nền qua ElevenLabs, lưu vào ``data/ai_music.wav``
    (đúng đường dẫn `resolve_existing_background()` đọc lại cho
    ``bg_mode="ai_music"``). Trả về ``{"creditCharged", "balanceAfter"}``.

    Raise :class:`MusicMatchError` nếu chưa cấu hình SaaS hoặc ffmpeg lỗi;
    để nguyên lỗi thật từ `saas_client` (InsufficientCreditError/SaasError/
    ...) bay lên — caller (GUI) tự phân biệt để hiện thông báo đúng.
    """
    if not is_available():
        raise MusicMatchError(
            "Tính năng nhạc nền AI cần máy chủ VoxDub (SaaS) — "
            "chưa cấu hình VOXDUB_API_URL.")
    from autodub.saas_client import get_client

    mp3_path = data_path(work_dir, "ai_music_raw.mp3", create_dir=True)
    wav_path = data_path(work_dir, "ai_music.wav")
    billing = get_client().generate_music(prompt, mp3_path, music_length_ms=music_length_ms)
    _mp3_to_wav(mp3_path, wav_path)
    return billing


def generate_sound_effect_preview(
    work_dir: str, description: str, name: str, *,
    duration_seconds: float | None = None,
) -> tuple[str, dict]:
    """Sinh 1 hiệu ứng âm thanh, lưu vào ``data/sfx_<name>.wav`` — TRẢ VỀ
    đường dẫn để GUI PREVIEW (nghe thử) TRƯỚC khi người dùng quyết định
    chèn vào video (Constraint 5 của V37 — không tự động chèn, luôn cho
    nghe thử trước). ``name`` PHẢI là định danh an toàn cho tên file (GUI
    tự sinh, không lấy trực tiếp từ input người dùng).
    """
    if not is_available():
        raise MusicMatchError(
            "Tính năng hiệu ứng âm thanh AI cần máy chủ VoxDub (SaaS) — "
            "chưa cấu hình VOXDUB_API_URL.")
    from autodub.saas_client import get_client

    mp3_path = data_path(work_dir, f"sfx_{name}.mp3", create_dir=True)
    wav_path = data_path(work_dir, f"sfx_{name}.wav")
    billing = get_client().generate_sound_effect(
        description, mp3_path, duration_seconds=duration_seconds)
    _mp3_to_wav(mp3_path, wav_path)
    return wav_path, billing


def insert_sfx_into_video(
    video_path: str, sfx_wav_path: str, timestamp_s: float,
    output_path: str, gain_db: float = -6.0,
) -> None:
    """Chèn 1 hiệu ứng âm thanh vào video ĐÃ CÓ (``dubbed_video.mp4``) tại
    ``timestamp_s`` — overlay qua ffmpeg (``adelay``+``amix``). Giữ nguyên
    track hình ảnh (``-c:v copy``), chỉ mã hoá lại audio.
    """
    delay_ms = max(0, int(timestamp_s * 1000))
    filter_complex = (
        f"[1:a]adelay={delay_ms}|{delay_ms},volume={gain_db}dB[sfx];"
        f"[0:a][sfx]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    result = subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-i", video_path, "-i", sfx_wav_path,
         "-filter_complex", filter_complex,
         "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         output_path],
        capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise MusicMatchError(
            f"Không chèn được hiệu ứng âm thanh: {(result.stderr or '')[-500:]}")


def insert_sfx_and_replace_video(
    work_dir: str, sfx_wav_path: str, timestamp_s: float, gain_db: float = -6.0,
) -> str:
    """Chèn hiệu ứng âm thanh vào ``dubbed_video.mp4`` hiện có của dự án,
    rồi thay thế bản cũ bằng bản mới. ffmpeg không đọc/ghi cùng lúc 1 file,
    nên dựng ra file tạm rồi ``os.replace`` (atomic trên cùng ổ đĩa) thay vì
    ghi đè trực tiếp. Trả về đường dẫn ``dubbed_video.mp4`` (không đổi).
    """
    dubbed = os.path.join(work_dir, "dubbed_video.mp4")
    if not os.path.isfile(dubbed):
        raise MusicMatchError(
            "Dự án này chưa có bản video đã ghép — hãy bấm Xuất video một "
            "lần trước khi chèn hiệu ứng âm thanh.")
    tmp_path = dubbed + ".sfx_tmp.mp4"
    insert_sfx_into_video(dubbed, sfx_wav_path, timestamp_s, tmp_path, gain_db)
    os.replace(tmp_path, dubbed)
    return dubbed
