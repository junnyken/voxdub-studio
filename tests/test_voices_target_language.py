"""Mini-spec V11 (docs/PLAN.md) — voices.catalog()/resolve() target-aware.

Trước V11, ``catalog()``/``resolve()``/``is_capcut_voice()`` luôn tra cứu
catalog CapCut vi-VN bất kể ``target`` đang dubbing sang ngôn ngữ nào — chọn
"Không Hề Tồn Tại" cho target=en vẫn rơi về một giọng vi-VN, và
``CapCutSynthesizer`` build cho target=en sẽ ``lookup()`` nhầm catalog tiếng
Việt rồi báo "không có giọng" cho một tên giọng en-US hoàn toàn hợp lệ.

Các bài dưới đây khoá lại hành vi ĐÚNG: catalog/resolve/is_capcut_voice/
CapCutSynthesizer đều phải tra đúng theo ngôn ngữ ĐÍCH thật, không mặc định
tiếng Việt khi target khác tiếng Việt được truyền vào tường minh. Không bài
nào gọi mạng.
"""
from __future__ import annotations

import os

import pytest

from autodub.config import ConfigError, Settings
from autodub.languages import get_target
from autodub.speech.tts import capcut_catalog, get_synthesizer, voices


@pytest.fixture(autouse=True)
def isolated_device(tmp_path, monkeypatch):
    monkeypatch.setattr(
        capcut_catalog, "device_file",
        lambda: str(tmp_path / "device" / "capcut_device.json"))


@pytest.fixture
def settings(tmp_path):
    """Máy chưa cài VieNeu — chỉ CapCut khả dụng, giống người dùng mới."""
    return Settings(vieneu_model_dir=str(tmp_path / "vieneu"))


def write_custom(settings, presets: dict) -> None:
    import json
    path = settings.vieneu_custom_voices_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"presets": presets}, f, ensure_ascii=False)


# ------------------------------------------------------- catalog() ------- #

def test_catalog_without_target_is_unchanged_vietnamese_default(settings):
    """target=None (0 regression) — vẫn custom + builtin + CapCut vi-VN."""
    names = {v.name for v in voices.catalog(settings)}
    assert names == set(capcut_catalog.names())


def test_catalog_target_vi_matches_default(settings):
    vi = get_target("vi")
    assert ({v.name for v in voices.catalog(settings, target=vi)}
            == {v.name for v in voices.catalog(settings)})


def test_catalog_target_en_returns_only_english_capcut_voices(settings):
    en = get_target("en")
    names = {v.name for v in voices.catalog(settings, target=en)}
    assert names == capcut_catalog.names(lang="en-US")
    assert names, "phải có ít nhất 1 giọng en-US khả dụng"
    # Không giọng tiếng Việt nào lẫn vào catalog tiếng Anh.
    assert not (names & capcut_catalog.names(lang="vi-VN"))


def test_catalog_target_en_ignores_vietnamese_custom_voices(settings):
    """Giọng offline tuỳ chỉnh (VieNeu tiếng Việt) không có nghĩa cho target
    tiếng Anh — VieNeu là model chuyên biệt tiếng Việt, không được lẫn vào."""
    write_custom(settings, {"Hoàng Nam": {"gender": "male",
                                          "source": "library"}})
    en = get_target("en")
    names = {v.name for v in voices.catalog(settings, target=en)}
    assert "Hoàng Nam" not in names


# ------------------------------------------------------- resolve() ------- #

def test_resolve_vietnamese_name_not_reused_for_english_target(settings):
    """Tên giọng vi-VN không tồn tại trong catalog en-US — resolve() không
    được trả nguyên tên đó cho target=en (trước V11 nó lờ đi target)."""
    en = get_target("en")
    vi_name = next(iter(capcut_catalog.names(lang="vi-VN")))
    resolved = voices.resolve(settings, vi_name, target=en)
    assert resolved != vi_name
    assert resolved in capcut_catalog.names(lang="en-US")


def test_resolve_english_name_round_trips(settings):
    en = get_target("en")
    en_name = next(iter(capcut_catalog.names(lang="en-US")))
    assert voices.resolve(settings, en_name, target=en) == en_name


# --------------------------------------------------- is_capcut_voice() --- #

def test_is_capcut_voice_respects_lang(settings):
    en_name = next(iter(capcut_catalog.names(lang="en-US")))
    vi_name = next(iter(capcut_catalog.names(lang="vi-VN")))
    assert voices.is_capcut_voice(en_name, lang="en-US") is True
    assert voices.is_capcut_voice(en_name, lang="vi-VN") is False
    assert voices.is_capcut_voice(vi_name, lang="en-US") is False


# ------------------------------------------------- get_synthesizer() ----- #

def test_get_synthesizer_english_target_picks_english_capcut_voice(settings):
    """Ca quan trọng nhất: dubbing sang tiếng Anh trên máy chưa cài VieNeu
    phải luôn ra CapCutSynthesizer với một giọng en-US thật, không rơi về
    giọng vi-VN hay ném ConfigError đòi cài VieNeu (VieNeu không đọc được
    tiếng Anh)."""
    en = get_target("en")
    synth = get_synthesizer(en, settings, voice=None)
    assert type(synth).__name__ == "CapCutSynthesizer"
    assert synth.voice_name in capcut_catalog.names(lang="en-US")


def test_get_synthesizer_english_target_never_requires_vieneu(settings):
    """VieNeu chưa cài (settings mặc định) không được chặn dubbing tiếng
    Anh — trước V11 mọi target đều tra catalog vi-VN nên có nguy cơ rơi về
    nhánh VieNeu và ném ConfigError oan."""
    en = get_target("en")
    try:
        get_synthesizer(en, settings, voice=None)
    except ConfigError:
        pytest.fail("target=en không được đòi cài VieNeu (engine tiếng Việt)")


# ------------------------------------------------- CapCutSynthesizer ----- #

def test_capcut_synthesizer_lang_param_routes_lookup(settings):
    from autodub.speech.tts.capcut_vi import CapCutSynthesizer

    en_name = next(iter(capcut_catalog.names(lang="en-US")))
    synth = CapCutSynthesizer(settings, voice_name=en_name, lang="en-US")
    assert synth.voice_name == en_name


def test_capcut_synthesizer_rejects_name_from_wrong_language(settings):
    """Tên giọng vi-VN không hợp lệ khi lang="en-US" — lookup() phải tra
    đúng catalog theo lang, không âm thầm rơi về mặc định vi-VN."""
    from autodub.speech.tts.capcut_vi import CapCutSynthesizer

    vi_name = next(iter(capcut_catalog.names(lang="vi-VN")))
    assert vi_name not in capcut_catalog.names(lang="en-US")
    with pytest.raises(ValueError):
        CapCutSynthesizer(settings, voice_name=vi_name, lang="en-US")


def test_capcut_synthesizer_default_lang_is_vietnamese_backward_compat(settings):
    """lang=None (0 regression) — hành vi y hệt trước V11."""
    from autodub.speech.tts.capcut_vi import CapCutSynthesizer

    vi_name = next(iter(capcut_catalog.names(lang="vi-VN")))
    synth = CapCutSynthesizer(settings, voice_name=vi_name)
    assert synth.voice_name == vi_name
