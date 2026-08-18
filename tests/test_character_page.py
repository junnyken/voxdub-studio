"""Mini-spec V62 — trang quản lý hồ sơ nhân vật.

Trọng tâm là những chỗ sai sẽ làm hỏng chính cơ chế khớp của V57–V61:

* hai nhân vật cùng tên phá `voice_for()`/`remember()` → phải chặn khi lưu,
* tên rỗng cũng vậy,
* cột "số tập"/"nhận diện" là số liệu hệ thống đo ra — gõ tay vào chỉ tạo dữ
  liệu sai, nên phải khoá,
* xoá nhân vật là hành động mất dữ liệu → phải hỏi lại.

Chạy:  QT_QPA_PLATFORM=offscreen pytest tests/test_character_page.py
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import autodub_gui.pages.character_page as cpage  # noqa: E402
from autodub.character_profile import Character, CharacterProfile  # noqa: E402
from autodub.config import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def profiles_dir(tmp_path):
    out = tmp_path / "out"
    directory = out / "character_profiles"
    CharacterProfile(
        name="Phim A",
        characters=[
            Character(name="SPEAKER_00", voice="Bùi Thiện", median_f0=115.0,
                      episodes=3, embedding=[1.0, 0.0]),
            Character(name="SPEAKER_01", voice="Bùi Trang", median_f0=205.0,
                      episodes=2),
        ],
        pronouns="tôi – anh",
    ).save(str(directory))
    return out


@pytest.fixture()
def page(app, profiles_dir):
    settings = Settings()
    settings.output_dir = str(profiles_dir)
    return cpage.CharacterPage(lambda: settings)


def test_lists_profiles_and_loads_the_first(page):
    assert page.profile_picker.count() == 1
    assert page.profile_picker.currentText() == "Phim A"
    assert page.table.rowCount() == 2
    assert page.table.item(0, cpage.COL_NAME).text() == "SPEAKER_00"
    assert page.pronouns.toPlainText() == "tôi – anh"


def test_shows_how_each_character_is_recognised(page):
    """Người dùng phải biết nhân vật nào đáng nghi: khớp bằng cao độ dễ lẫn
    với người cùng giới, khớp bằng embedding thì không."""
    assert "chính xác" in page.table.item(0, cpage.COL_MATCH).text()
    assert "dễ lẫn" in page.table.item(1, cpage.COL_MATCH).text()


def test_measured_columns_are_read_only(page):
    """Số tập và cách nhận diện do hệ thống đo — gõ tay vào chỉ tạo dữ liệu sai."""
    for col in (cpage.COL_EPISODES, cpage.COL_MATCH):
        item = page.table.item(0, col)
        assert not (item.flags() & Qt.ItemIsEditable), f"cột {col} phải khoá"


def test_renaming_a_character_persists(page, profiles_dir, monkeypatch):
    monkeypatch.setattr(cpage.TOASTS, "info", lambda *a, **k: None)
    page.table.item(0, cpage.COL_NAME).setText("Lý Tứ")
    page.table.item(0, cpage.COL_VOICE).setText("Phạm Tuyên")

    page._save()

    reloaded = CharacterProfile.load(
        str(profiles_dir / "character_profiles"), "Phim A")
    assert reloaded.characters[0].name == "Lý Tứ"
    assert reloaded.voice_for("Lý Tứ") == "Phạm Tuyên"
    assert reloaded.characters[0].episodes == 3, "số liệu đo được phải giữ nguyên"
    assert reloaded.characters[0].embedding == [1.0, 0.0], "embedding không được mất"


def test_duplicate_names_are_refused(page, profiles_dir, monkeypatch):
    """Hai nhân vật cùng tên phá chính cơ chế khớp — `voice_for()` lấy cái
    đầu tiên, `remember()` cập nhật nhầm người."""
    warned = []
    monkeypatch.setattr(cpage.TOASTS, "warn", lambda m, *a, **k: warned.append(m))
    page.table.item(1, cpage.COL_NAME).setText("SPEAKER_00")

    page._save()

    assert warned and "trùng" in warned[0].lower()
    reloaded = CharacterProfile.load(
        str(profiles_dir / "character_profiles"), "Phim A")
    assert reloaded.characters[1].name == "SPEAKER_01", "không được ghi đè hồ sơ"


def test_empty_name_is_refused(page, profiles_dir, monkeypatch):
    warned = []
    monkeypatch.setattr(cpage.TOASTS, "warn", lambda m, *a, **k: warned.append(m))
    page.table.item(0, cpage.COL_NAME).setText("   ")

    page._save()

    assert warned and "trống" in warned[0].lower()


def test_delete_asks_first_and_respects_cancel(page, monkeypatch):
    monkeypatch.setattr(cpage.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (False, None)))
    page.table.setCurrentCell(0, cpage.COL_NAME)

    page._delete_selected()

    assert page.table.rowCount() == 2, "bấm Huỷ thì không được xoá gì"


def test_delete_removes_the_character_when_confirmed(page, profiles_dir, monkeypatch):
    monkeypatch.setattr(cpage.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (True, None)))
    monkeypatch.setattr(cpage.TOASTS, "info", lambda *a, **k: None)
    page.table.setCurrentCell(0, cpage.COL_NAME)

    page._delete_selected()
    page._save()

    reloaded = CharacterProfile.load(
        str(profiles_dir / "character_profiles"), "Phim A")
    assert [c.name for c in reloaded.characters] == ["SPEAKER_01"]


def test_delete_without_selection_warns_instead_of_crashing(page, monkeypatch):
    warned = []
    monkeypatch.setattr(cpage.TOASTS, "warn", lambda m, *a, **k: warned.append(m))
    page.table.setCurrentCell(-1, -1)

    page._delete_selected()

    assert warned


def test_page_with_no_profiles_explains_how_to_create_one(app, tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path / "trong")
    empty = cpage.CharacterPage(lambda: settings)

    assert empty.profile_picker.count() == 0
    assert not empty.empty_note.isHidden()
    assert not empty.btn_save.isEnabled(), "không có hồ sơ thì không cho lưu"


def test_switching_profile_with_unsaved_edits_asks_first(page, monkeypatch,
                                                         profiles_dir):
    """Bug tự soi ra khi rà lại V62: bản đầu đổi series là nạp đè, thứ vừa gõ
    biến mất không một lời nào — mất dữ liệu âm thầm là kiểu tệ nhất."""
    CharacterProfile(name="Phim B",
                     characters=[Character(name="X", voice="V")]).save(
        str(profiles_dir / "character_profiles"))
    page.reload()

    page.table.item(0, cpage.COL_NAME).setText("Đang sửa dở")
    asked = []

    def _ask(*_a, **_k):
        asked.append(True)
        return (False, None)

    monkeypatch.setattr(cpage.ConfirmDialog, "ask", staticmethod(_ask))
    page.profile_picker.setCurrentText("Phim B")

    assert asked, "phải hỏi trước khi bỏ thay đổi"
    assert page.profile_picker.currentText() == "Phim A", (
        "bấm «Ở lại để lưu» thì phải quay về đúng hồ sơ đang sửa"
    )
    assert page.table.item(0, cpage.COL_NAME).text() == "Đang sửa dở"


def test_switching_after_saving_does_not_ask(page, monkeypatch, profiles_dir):
    CharacterProfile(name="Phim B",
                     characters=[Character(name="X", voice="V")]).save(
        str(profiles_dir / "character_profiles"))
    page.reload()

    monkeypatch.setattr(cpage.TOASTS, "info", lambda *a, **k: None)
    page.table.item(0, cpage.COL_NAME).setText("Lý Tứ")
    page._save()

    asked = []

    def _ask(*_a, **_k):
        asked.append(True)
        return (True, None)

    monkeypatch.setattr(cpage.ConfirmDialog, "ask", staticmethod(_ask))
    page.profile_picker.setCurrentText("Phim B")

    assert not asked, "đã lưu rồi thì đừng hỏi nữa"
    assert page.profile_picker.currentText() == "Phim B"



# ------------------------------------------------------------------ V68 --
def test_gop_hai_nhan_vat_bi_tach_nham(page):
    """Gộp phải cộng dồn số tập và vẽ lại bảng NGAY, không đọc đè từ đĩa.

    `_load()` đọc lại file; nếu nút Gộp gọi nó để vẽ lại thì đúng thay đổi vừa
    làm bị nuốt mất không một lời nào. Đây là lý do V68 tách `_render_table`.
    """
    assert page.table.rowCount() == 2
    assert page._profile.merge_characters("SPEAKER_00", "SPEAKER_01") is True
    page._render_table()

    assert page.table.rowCount() == 1, "bảng phải theo bộ nhớ, không theo đĩa"
    assert page.table.item(0, 0).text() == "SPEAKER_00"
    assert page.table.item(0, 2).text() == "5", "3 tập + 2 tập phải cộng dồn"


def test_hoc_lai_doi_cot_nhan_dien_ve_cao_do(page):
    assert "chính xác" in page.table.item(0, 3).text().lower()

    assert page._profile.forget_embedding("SPEAKER_00") is True
    page._render_table()

    assert "cao độ" in page.table.item(0, 3).text().lower(), \
        "xoá phần đã học rồi thì cột Nhận diện phải nói thật là chỉ còn cao độ"


def test_ve_lai_bang_khong_tu_dat_co_da_sua(page):
    """`_render_table` chỉ vẽ — không được tự bật cờ dirty qua itemChanged."""
    page._dirty = False
    page._render_table()
    assert page._dirty is False
