"""Mini-spec V37 (docs/PLAN.md, Phase G) — orchestration nhạc nền/SFX AI.
Mock `saas_client`/ffmpeg subprocess — KHÔNG gọi ElevenLabs thật (tốn tiền
thật), KHÔNG cần ffmpeg thật cài trong môi trường test."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from autodub.media import music_match


@pytest.fixture
def fake_ffmpeg_ok(monkeypatch):
    def _fake_run(cmd, **kwargs):
        # Tự ghi 1 file rỗng ở đường dẫn output cuối cùng để mô phỏng
        # ffmpeg thật đã chạy xong — các hàm gọi sau (kiểm tồn tại file)
        # vẫn hoạt động đúng.
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake-wav-or-video-bytes")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", _fake_run)


@pytest.fixture
def fake_ffmpeg_fail(monkeypatch):
    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="ffmpeg lỗi giả lập")
    monkeypatch.setattr(subprocess, "run", _fake_run)


def test_is_available_follows_saas_configured(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    assert music_match.is_available() is True
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    assert music_match.is_available() is False


def test_generate_and_save_music_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    with pytest.raises(music_match.MusicMatchError, match="SaaS"):
        music_match.generate_and_save_music(str(tmp_path), "nhạc vui tươi")


def test_generate_and_save_music_writes_ai_music_wav(tmp_path, monkeypatch, fake_ffmpeg_ok):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    fake_client = MagicMock()
    fake_client.generate_music.return_value = {"creditCharged": 500, "balanceAfter": 500}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)

    result = music_match.generate_and_save_music(str(tmp_path), "nhạc buồn, chậm rãi")

    assert result == {"creditCharged": 500, "balanceAfter": 500}
    fake_client.generate_music.assert_called_once()
    call_args = fake_client.generate_music.call_args
    assert call_args.args[0] == "nhạc buồn, chậm rãi"

    from autodub.workdir import data_path
    wav_path = data_path(str(tmp_path), "ai_music.wav")
    assert __import__("os").path.isfile(wav_path)


def test_generate_and_save_music_ffmpeg_failure_raises(tmp_path, monkeypatch, fake_ffmpeg_fail):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    fake_client = MagicMock()
    fake_client.generate_music.return_value = {"creditCharged": 500, "balanceAfter": 500}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)

    with pytest.raises(music_match.MusicMatchError, match="MP3 sang WAV"):
        music_match.generate_and_save_music(str(tmp_path), "nhạc buồn")


def test_generate_and_save_music_propagates_saas_errors(tmp_path, monkeypatch):
    """Lỗi thật từ saas_client (hết Vox, mất mạng...) phải bay nguyên lên
    caller, KHÔNG bị nuốt thành MusicMatchError chung chung — GUI cần phân
    biệt để hiện đúng thông báo (vd InsufficientCreditError -> hiện nút nạp Vox)."""
    from autodub.saas_client import InsufficientCreditError

    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    fake_client = MagicMock()
    fake_client.generate_music.side_effect = InsufficientCreditError(
        "hết Vox", balance=10, required=500)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)

    with pytest.raises(InsufficientCreditError):
        music_match.generate_and_save_music(str(tmp_path), "nhạc vui")


def test_generate_sound_effect_preview_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    with pytest.raises(music_match.MusicMatchError, match="SaaS"):
        music_match.generate_sound_effect_preview(str(tmp_path), "tiếng vỗ tay", "clap1")


def test_generate_sound_effect_preview_returns_path_and_billing(tmp_path, monkeypatch, fake_ffmpeg_ok):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    fake_client = MagicMock()
    fake_client.generate_sound_effect.return_value = {"creditCharged": 100, "balanceAfter": 900}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)

    path, billing = music_match.generate_sound_effect_preview(
        str(tmp_path), "tiếng vỗ tay", "clap1", duration_seconds=2.0)

    assert billing == {"creditCharged": 100, "balanceAfter": 900}
    assert path.endswith("sfx_clap1.wav")
    import os
    assert os.path.isfile(path)


def test_insert_sfx_into_video_success(tmp_path, fake_ffmpeg_ok):
    video_in = str(tmp_path / "in.mp4")
    sfx_wav = str(tmp_path / "sfx.wav")
    output = str(tmp_path / "out.mp4")
    for p in (video_in, sfx_wav):
        with open(p, "wb") as f:
            f.write(b"x")

    music_match.insert_sfx_into_video(video_in, sfx_wav, 12.5, output)

    import os
    assert os.path.isfile(output)


def test_insert_sfx_into_video_ffmpeg_failure_raises(tmp_path, fake_ffmpeg_fail):
    with pytest.raises(music_match.MusicMatchError, match="chèn được"):
        music_match.insert_sfx_into_video(
            str(tmp_path / "in.mp4"), str(tmp_path / "sfx.wav"), 5.0, str(tmp_path / "out.mp4"))


def test_insert_sfx_and_replace_video_missing_dubbed_raises(tmp_path):
    with pytest.raises(music_match.MusicMatchError, match="chưa có bản video"):
        music_match.insert_sfx_and_replace_video(str(tmp_path), str(tmp_path / "sfx.wav"), 3.0)


def test_insert_sfx_and_replace_video_overwrites_in_place(tmp_path, fake_ffmpeg_ok):
    import os

    dubbed = tmp_path / "dubbed_video.mp4"
    dubbed.write_bytes(b"old-video-bytes")
    sfx = tmp_path / "sfx.wav"
    sfx.write_bytes(b"x")

    result = music_match.insert_sfx_and_replace_video(str(tmp_path), str(sfx), 3.0)

    assert result == str(dubbed)
    assert os.path.isfile(dubbed)
    # File tạm không còn sót lại sau khi thay thế xong.
    assert not os.path.isfile(str(dubbed) + ".sfx_tmp.mp4")


def test_insert_sfx_negative_timestamp_clamped_to_zero(tmp_path, monkeypatch):
    """Timestamp âm (lỗi logic caller) không được ra lệnh ffmpeg vô nghĩa —
    kẹp về 0 thay vì crash hay tạo delay âm không hợp lệ."""
    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"x")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", _fake_run)

    music_match.insert_sfx_into_video(
        str(tmp_path / "in.mp4"), str(tmp_path / "sfx.wav"), -3.0, str(tmp_path / "out.mp4"))

    filter_arg = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
    assert "adelay=0|0" in filter_arg
