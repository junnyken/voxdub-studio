"""V68 — sửa tay hồ sơ nhân vật: gộp hai người bị tách nhầm, xoá embedding bẩn.

Đo ngày 18-08 cho thấy hai lỗi ngược nhau và KHÔNG lỗi nào chỉnh ngưỡng mà
khỏi được:

- pyannote gộp 3 giọng nữ thành 1 nhãn → embedding của nhân vật đó là bản trộn
  của nhiều người, càng dùng càng khớp sai → `forget_embedding()`.
- nhãn diarization đổi giữa các tập → một người thành hai nhân vật →
  `merge_characters()`.
"""
from __future__ import annotations

from autodub.character_profile import CharacterProfile


def _ho_so(tmp_path):
    return CharacterProfile.load(str(tmp_path), "Phim Thử")


def _them(hs, ten, f0, voice, embedding, episodes=1, gender=""):
    hs.remember({ten: ten}, {ten: f0}, {ten: voice},
                {ten: gender}, {ten: embedding})
    for c in hs.characters:
        if c.name == ten:
            c.episodes = episodes
    return hs


# ------------------------------------------------------------------- gộp
def test_gop_cong_don_so_tap(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "Lý Tứ", 120.0, "v1", [1.0, 0.0], episodes=9)
    _them(hs, "Lý Tứ (2)", 122.0, "v2", [0.0, 1.0], episodes=1)

    assert hs.merge_characters("Lý Tứ", "Lý Tứ (2)") is True
    con_lai = {c.name: c for c in hs.characters}
    assert set(con_lai) == {"Lý Tứ"}
    assert con_lai["Lý Tứ"].episodes == 10


def test_gop_TRON_embedding_theo_trong_so_so_tap(tmp_path):
    """Người xuất hiện 9 tập đáng tin hơn người 1 tập — không lấy trung bình đều."""
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [1.0, 0.0], episodes=9)
    _them(hs, "B", 120.0, "v2", [0.0, 1.0], episodes=1)

    hs.merge_characters("A", "B")
    v = {c.name: c for c in hs.characters}["A"].embedding
    assert v[0] > v[1], "phía 9 tập phải nặng hơn hẳn phía 1 tập"


def test_gop_khong_lam_mat_embedding_khi_ben_giu_lai_chua_co(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [], episodes=1)
    _them(hs, "B", 130.0, "v2", [0.6, 0.8], episodes=1)

    hs.merge_characters("A", "B")
    v = {c.name: c for c in hs.characters}["A"].embedding
    assert v, "bên bị gộp có embedding thì phải giữ lại, xoá là mất trắng dữ liệu đã học"


def test_gop_giu_giong_cua_ben_giu_lai(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "giong_A", [1.0, 0.0])
    _them(hs, "B", 121.0, "giong_B", [0.9, 0.1])

    hs.merge_characters("A", "B")
    assert {c.name: c for c in hs.characters}["A"].voice == "giong_A"


def test_gop_ten_khong_ton_tai_tra_False(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [1.0, 0.0])
    assert hs.merge_characters("A", "Không Có") is False
    assert hs.merge_characters("Không Có", "A") is False


def test_gop_chinh_no_tra_False_khong_xoa_mat(tmp_path):
    """Gộp A vào A mà không chặn thì vòng lọc cuối xoá luôn A."""
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [1.0, 0.0])
    assert hs.merge_characters("A", "A") is False
    assert [c.name for c in hs.characters] == ["A"]


# ------------------------------------------------ xoá embedding đã bẩn
def test_xoa_embedding_giu_ten_giong_va_so_tap(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "giong_A", [1.0, 0.0], episodes=5)

    assert hs.forget_embedding("A") is True
    c = {x.name: x for x in hs.characters}["A"]
    assert c.embedding == []
    assert c.voice == "giong_A", "giọng người dùng chọn không được đụng tới"
    assert c.episodes == 5, "số tập là lịch sử có thật, không phải thứ bị bẩn"
    assert c.median_f0 == 120.0, "cao độ vẫn dùng được để khớp tạm"


def test_xoa_embedding_khi_von_khong_co_tra_False(tmp_path):
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [])
    assert hs.forget_embedding("A") is False


def test_xoa_embedding_ten_khong_ton_tai_tra_False(tmp_path):
    assert _ho_so(tmp_path).forget_embedding("Không Có") is False


def test_sau_khi_sua_luu_va_doc_lai_van_dung(tmp_path):
    """Sửa mà không sống sót qua lần lưu thì vô nghĩa."""
    hs = _ho_so(tmp_path)
    _them(hs, "A", 120.0, "v1", [1.0, 0.0], episodes=3)
    _them(hs, "B", 121.0, "v2", [0.9, 0.1], episodes=2)
    hs.merge_characters("A", "B")
    hs.forget_embedding("A")
    hs.save(str(tmp_path))

    lai = CharacterProfile.load(str(tmp_path), "Phim Thử")
    assert [c.name for c in lai.characters] == ["A"]
    assert lai.characters[0].episodes == 5
    assert lai.characters[0].embedding == []
