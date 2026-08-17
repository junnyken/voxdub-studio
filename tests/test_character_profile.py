"""Mini-spec V57 — hồ sơ nhân vật dùng lại qua nhiều tập.

Nguyên tắc chi phối mọi test ở đây: **khớp sai tệ hơn không khớp**. Gán nhầm
giọng của nhân vật khác vào một người lạ làm hỏng cả tập theo cách người dùng
chỉ phát hiện sau khi đã nghe lại — nên nhóm test "KHÔNG được khớp" quan
trọng ngang nhóm "phải khớp".

Chạy:  pytest tests/test_character_profile.py
"""
from __future__ import annotations

import json

import pytest

from autodub.character_profile import (
    MATCH_TOLERANCE_HZ,
    Character,
    CharacterProfile,
)


def _profile(**kw) -> CharacterProfile:
    return CharacterProfile(
        name="Phim A",
        characters=[
            Character(name="Nam chính", voice="Bùi Thiện", median_f0=115.0,
                      gender="male", episodes=3),
            Character(name="Nữ chính", voice="Bùi Trang", median_f0=205.0,
                      gender="female", episodes=3),
        ],
        **kw,
    )


# --- Khớp ĐÚNG -----------------------------------------------------------

def test_same_person_next_episode_gets_the_same_voice():
    """Đây là lý do V57 tồn tại: tập 2 phải nhận lại đúng giọng tập 1.

    Nhãn diarization đổi (`SPEAKER_00` → `SPEAKER_01`) là chuyện bình thường
    giữa 2 file — khớp phải dựa vào giọng, không dựa vào nhãn.
    """
    profile = _profile()

    matched = profile.match_speakers({"SPEAKER_01": 117.0, "SPEAKER_00": 203.0})

    assert matched == {"SPEAKER_01": "Nam chính", "SPEAKER_00": "Nữ chính"}
    assert profile.voice_for("Nam chính") == "Bùi Thiện"


def test_small_recording_differences_still_match():
    profile = _profile()
    inside = 115.0 + MATCH_TOLERANCE_HZ - 1

    assert profile.match_speakers({"S0": inside}) == {"S0": "Nam chính"}


# --- KHÔNG được khớp ------------------------------------------------------

def test_a_stranger_is_not_forced_onto_an_existing_character():
    profile = _profile()
    outside = 115.0 + MATCH_TOLERANCE_HZ + 5

    assert profile.match_speakers({"S0": outside}) == {}, (
        "ngoài ngưỡng thì phải coi là người mới, không gán bừa giọng cũ"
    )


def test_speaker_without_usable_audio_is_skipped():
    """F0 = 0 nghĩa là không đủ dữ liệu voiced — không đoán (đúng nếp V36)."""
    profile = _profile()

    assert profile.match_speakers({"S0": 0.0}) == {}


def test_two_speakers_near_one_character_only_one_matches():
    """Một-đối-một: nếu không, 2 người nói sẽ cùng nhận một giọng — đúng cái
    lỗi mà tính năng này sinh ra để tránh."""
    profile = _profile()

    matched = profile.match_speakers({"S0": 114.0, "S1": 116.0})

    assert len(matched) == 1
    assert list(matched.values()) == ["Nam chính"]
    assert matched.get("S0") == "Nam chính", "người gần nhất phải thắng"


def test_empty_profile_matches_nothing():
    assert CharacterProfile(name="Mới").match_speakers({"S0": 120.0}) == {}


# --- Ghi nhớ sau mỗi tập --------------------------------------------------

def test_pitch_is_smoothed_not_overwritten():
    """Một tập thu âm tệ không được kéo lệch hồ sơ đã đúng qua nhiều tập."""
    profile = _profile()

    profile.remember({"S0": "Nam chính"}, {"S0": 135.0}, {"S0": "Bùi Thiện"})

    nam = next(c for c in profile.characters if c.name == "Nam chính")
    assert 115.0 < nam.median_f0 < 125.0, (
        f"F0 phải nhích nhẹ chứ không nhảy hẳn sang 135 (đang {nam.median_f0})"
    )
    assert nam.episodes == 4


def test_new_speaker_becomes_a_new_character():
    profile = _profile()

    profile.remember({}, {"SPEAKER_09": 160.0}, {"SPEAKER_09": "Bùi Vân"})

    names = [c.name for c in profile.characters]
    assert "SPEAKER_09" in names, "người lạ phải được thêm làm nhân vật mới"
    new = next(c for c in profile.characters if c.name == "SPEAKER_09")
    assert new.voice == "Bùi Vân"
    assert new.median_f0 == 160.0
    assert new.episodes == 1


def test_voice_change_is_remembered_for_next_episode():
    """Người dùng đổi giọng cho nhân vật ở tập này → tập sau dùng giọng mới."""
    profile = _profile()

    profile.remember({"S0": "Nam chính"}, {"S0": 115.0}, {"S0": "Phạm Tuyên"})

    assert profile.voice_for("Nam chính") == "Phạm Tuyên"


# --- Lưu trữ ---------------------------------------------------------------

def test_round_trip_keeps_everything(tmp_path):
    profile = _profile(pronouns="tôi – anh", glossary="显卡 = card đồ họa",
                       context="phim cổ trang")
    profile.save(str(tmp_path))

    loaded = CharacterProfile.load(str(tmp_path), "Phim A")

    assert loaded.pronouns == "tôi – anh"
    assert loaded.glossary == "显卡 = card đồ họa"
    assert loaded.context == "phim cổ trang"
    assert [c.name for c in loaded.characters] == ["Nam chính", "Nữ chính"]
    assert loaded.voice_for("Nữ chính") == "Bùi Trang"


def test_missing_profile_loads_empty_instead_of_failing(tmp_path):
    loaded = CharacterProfile.load(str(tmp_path), "Chưa từng có")

    assert loaded.characters == []
    assert loaded.name == "Chưa từng có"


def test_corrupt_profile_degrades_and_is_never_overwritten(tmp_path):
    """Hồ sơ hỏng không được làm sập lượt dub, và cũng không được đè lên.

    File của người dùng có thể chỉ lỗi cú pháp nhỏ mà họ tự sửa được — ghi đè
    là xoá mất công sức của họ.
    """
    path = CharacterProfile.path_for(str(tmp_path), "Phim A")
    path_obj = tmp_path / "phim-a.json"
    path_obj.write_text("{ hỏng cú pháp", encoding="utf-8")

    loaded = CharacterProfile.load(str(tmp_path), "Phim A")
    assert loaded.characters == [], "phải chạy tiếp như chưa có hồ sơ"

    loaded.remember({}, {"S0": 120.0}, {"S0": "X"})
    assert loaded.save(str(tmp_path)) == "", "không được ghi đè hồ sơ hỏng"
    assert path_obj.read_text(encoding="utf-8") == "{ hỏng cú pháp"
    assert path == str(path_obj)


def test_profile_file_is_human_editable_json(tmp_path):
    """Người dùng phải đổi được tên nhân vật bằng tay — đó là lý do dùng JSON
    dễ đọc chứ không phải định dạng nhị phân."""
    profile = _profile()
    profile.save(str(tmp_path))

    raw = json.loads((tmp_path / "phim-a.json").read_text(encoding="utf-8"))
    assert raw["characters"][0]["name"] == "Nam chính"
    raw["characters"][0]["name"] = "Lý Tứ"
    (tmp_path / "phim-a.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    reloaded = CharacterProfile.load(str(tmp_path), "Phim A")
    assert [c.name for c in reloaded.characters] == ["Lý Tứ", "Nữ chính"]
