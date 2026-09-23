"""D1 — hình chạy theo GIỌNG ĐỌC THẬT, không theo ước lượng.

`dung_du_an()` dựng slideshow theo ƯỚC LƯỢNG thời gian đọc. Giọng thật lệch
~5% (pilot H4 đo: 19,30s so với 20,31s), và vì các đoạn kịch bản NỐI LIỀN
NHAU — không có khoảng lặng nào để dồn trễ — phần lệch ấy **cộng dồn**: càng
về cuối hình càng chạy trước lời.

Engine vốn xử lý bằng cách NÉN GIỌNG cho vừa chỗ (`timing_max_atempo`). Với
video quay thì đúng. Với slideshow thì ngược mới đúng: ảnh tĩnh không có nhịp
riêng, giữ 2,0 hay 2,3 giây đều không ai nhận ra.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import du_an_tu_kich_ban as dk


def _ghi_nguon(work_dir, anh, giay_chuyen=0.0, kieu_chuyen=None):
    from autodub.workdir import data_path
    duong = data_path(work_dir, dk.TEN_NGUON_GOC, create_dir=True)
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    noi_dung = {"anh_moi_doan": anh, "giay_chuyen": giay_chuyen}
    # `kieu_chuyen=None` = dự án dựng TRƯỚC I5: khoá này không tồn tại. Giữ
    # được ca đó là cách duy nhất biết dự án cũ còn mở lại được.
    if kieu_chuyen is not None:
        noi_dung["kieu_chuyen"] = kieu_chuyen
    with open(duong, "w", encoding="utf-8") as f:
        json.dump(noi_dung, f)
    return duong


def _anh(tmp_path, n):
    ra = []
    for i in range(n):
        p = tmp_path / f"anh{i}.png"
        p.write_bytes(b"\x89PNG-gia")
        ra.append(str(p))
    return ra


def _segments(moc_va_cuoi):
    """`[(start, end), …]` → danh sách câu như editor truyền vào."""
    return [{"id": i + 1, "start": a, "end": b}
            for i, (a, b) in enumerate(moc_va_cuoi)]


class _Ghep:
    """Ghi lại lời gọi ghép, không chạy ffmpeg."""

    def __init__(self):
        self.goi = []

    def __call__(self, duong_anh, duong_ra, *, giay_moi_anh, giay_chuyen=0.3,
                 kieu_chuyen="mo_chong"):
        self.goi.append({"anh": list(duong_anh), "giay": list(giay_moi_anh),
                         "ra": duong_ra, "chuyen": giay_chuyen,
                         "kieu": kieu_chuyen})
        with open(duong_ra, "wb") as f:
            f.write(b"video gia")
        return duong_ra


# ================================================================
# Chuyện chính: hình đi theo mốc THẬT
# ================================================================

def test_dung_lai_theo_dung_moc_that_cua_tung_cau(tmp_path):
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    anh = _anh(tmp_path, 3)
    _ghi_nguon(wd, anh)
    # Ước lượng cũ 2+2+2; giọng thật 2,5 + 3,0 + 2,0.
    segs = _segments([(0.0, 2.5), (2.5, 5.5), (5.5, 7.5)])
    ghep = _Ghep()

    ra = dk.dung_lai_video_theo_giong(
        wd, segs, ghep_video=ghep, do_thoi_luong=lambda _p: 7.5)

    assert ra and os.path.basename(ra) == dk.TEN_VIDEO_NGUON
    assert ghep.goi[-1]["giay"] == pytest.approx([2.5, 3.0, 2.0])


def test_giay_chuyen_lay_lai_DUNG_bang_luc_dung_lan_dau(tmp_path):
    """Đổi kiểu chuyển cảnh giữa chừng thì `xfade` ăn mất thời lượng khác đi
    và cổng H4c-1 sẽ báo lệch — phải dùng lại đúng con số đã ghi."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2), giay_chuyen=0.45)
    ghep = _Ghep()
    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.0)
    assert ghep.goi[-1]["chuyen"] == pytest.approx(0.45)


# ================================================================
# CHỐT AN TOÀN — đây là đường xuất của MỌI dự án
# ================================================================

def test_du_an_LONG_TIENG_THUONG_khong_bi_dung_lai(tmp_path):
    """Không có tệp truy nguồn ⇒ không phải dự án dựng từ kịch bản. Dựng lại
    ở đây nghĩa là thay video quay thật của người ta bằng một slideshow."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0)]), ghep_video=ghep) is None
    assert ghep.goi == [], "đã đụng vào dự án không phải của mình"


def test_du_an_dung_bang_BAN_CU_khong_co_danh_sach_anh(tmp_path):
    """Dự án dựng trước D1 không ghi `anh_moi_doan`. Không phải lỗi — chỉ là
    không làm được, và phải im lặng giữ nguyên."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    from autodub.workdir import data_path
    duong = data_path(wd, dk.TEN_NGUON_GOC, create_dir=True)
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    with open(duong, "w", encoding="utf-8") as f:
        json.dump({"brand_script_id": "x", "so_doan": 2}, f)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_so_anh_KHAC_so_cau_thi_bo_qua(tmp_path):
    """Người dùng sửa kịch bản thêm/bớt câu — ghép theo thứ tự nữa là ảnh lên
    nhầm đoạn."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_anh_bi_XOA_hoac_DOI_CHO_thi_bo_qua(tmp_path):
    """Ảnh là tệp của người dùng — họ có quyền dọn ổ đĩa."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    anh = _anh(tmp_path, 2)
    os.unlink(anh[1])
    _ghi_nguon(wd, anh)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_MOC_KHONG_TANG_DAN_thi_bo_qua_chu_khong_doan(tmp_path):
    """Không lát kín được dòng thời gian thì giữ nguyên, đừng đoán.

    Chú ý ĐÚNG điều kiện: hai câu *chồng tiếng* (``end`` lấn sang câu sau) vẫn
    lát kín được, vì cảnh chỉ cần đổi tại ``start`` của câu kế. Ca thật sự
    hỏng là **mốc không tăng dần** — lúc đó có cảnh dài 0 hoặc âm.

    (Bản đầu của test này dùng dữ liệu chồng tiếng và đỏ: tiền đề của tôi sai,
    không phải mã sai.)
    """
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 4.0), (4.0, 5.0), (4.0, 7.0)]),
        ghep_video=ghep) is None
    assert ghep.goi == []


def test_chong_tieng_VAN_lat_kin_duoc_vi_canh_doi_tai_start(tmp_path):
    """Chốt đi kèm test trên: đừng chặn oan ca chồng tiếng bình thường."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    ra = dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 4.0), (2.0, 5.5), (5.0, 7.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 7.0)
    assert ra is not None
    assert ghep.goi[-1]["giay"] == pytest.approx([2.0, 3.0, 2.0])


def test_DUNG_SUA_QUA_TAY_uoc_luong_da_dung_thi_KHONG_dung_lai(tmp_path):
    """Dựng lại tốn hàng chục giây ffmpeg. Thay một tệp đang đúng bằng một tệp
    cũng đúng là rủi ro không đổi lại được gì."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    with open(os.path.join(wd, dk.TEN_VIDEO_NGUON), "wb") as f:
        f.write(b"video cu")
    ghep = _Ghep()
    # Giọng thật 6,0 giây, video đang có 6,05 giây — lệch 0,05 < ngưỡng.
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.05) is None
    assert ghep.goi == []


def test_lech_VUA_DU_nguong_thi_van_dung_lai(tmp_path):
    """Chốt của chốt trên: ngưỡng phải là ngưỡng thật, không phải cái cớ để
    không bao giờ dựng lại."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    with open(os.path.join(wd, dk.TEN_VIDEO_NGUON), "wb") as f:
        f.write(b"video cu")
    ghep = _Ghep()
    goi = {"n": 0}

    def do(_p):
        goi["n"] += 1
        return 5.0 if goi["n"] == 1 else 6.0     # lượt 1: video cũ; lượt 2: mới

    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=do) is not None
    assert ghep.goi


def test_cong_thoi_luong_H4c1_VAN_CHAY_tren_video_moi(tmp_path):
    """Dựng lại mà lệch thì phải hỏng TO TIẾNG, không âm thầm ghi đè một video
    sai lên một video đúng."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    ghep = _Ghep()
    with pytest.raises(dk.VideoLechThoiLuong):
        dk.dung_lai_video_theo_giong(
            wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
            ghep_video=ghep, do_thoi_luong=lambda _p: 99.0)


# ================================================================
# Nối dây: dung_du_an có GIỮ danh sách ảnh không
# ================================================================

def test_dung_du_an_GHI_LAI_danh_sach_anh_va_giay_chuyen(tmp_path):
    """Trước D1, hàm này dựng video xong rồi VỨT danh sách ảnh đi — nên về sau
    không còn gì để dựng lại."""
    wd = str(tmp_path / "duan")
    anh = _anh(tmp_path, 2)
    kich_ban = {"status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": "Một hai ba."},
        {"beatType": "cta", "voiceoverTextVi": "Bốn năm sáu bảy."}]}
    from autodub.storyboard import dung_storyboard
    tong = dung_storyboard(kich_ban).tong_giay

    dk.dung_du_an(kich_ban, anh, wd, giay_chuyen=0.4,
                  ghep_video=_Ghep(), do_thoi_luong=lambda _p: tong)

    from autodub.workdir import data_path
    with open(data_path(wd, dk.TEN_NGUON_GOC), encoding="utf-8") as f:
        nguon = json.load(f)
    assert nguon["anh_moi_doan"] == anh
    assert nguon["giay_chuyen"] == pytest.approx(0.4)


# ================================================================
# CẢNH CUỐI phải phủ hết TIẾNG, không tắt ở chữ cuối cùng
# ================================================================
#
# Số đo THẬT, lấy từ một lượt `scripts/pilot_h4_cuc_bo.py --giu` chạy 21/09
# (không phải số bịa cho vừa test):
#
#   ước lượng  : câu bắt đầu 0 / 6,44 / 13,88 — kịch bản dài 19,31s
#   giọng thật : 3,216 / 3,528 / 2,472s  (VieNeu đọc NHANH hơn ước lượng)
#   sau `apply_soft_timing`: start GIỮ NGUYÊN (nó chỉ dồn trễ, không kéo câu
#       lên sớm), `end` bị kéo về đúng chỗ tiếng tắt → 3,216 / 9,968 / 16,352
#   tiếng đã ghép: `data/audio_vi_full.wav` = **20,31s** — vì
#       `editor.rebuild_output` tính `total_duration = max(end) + 1.0` TRƯỚC
#       bước đặt lại thời điểm, nên nó vẫn theo ước lượng (19,31 + 1,0).
#
# Mọi test D1 cũ đều dùng câu NỐI LIỀN NHAU (`end[i] == start[i+1]`) — hình
# dạng mà `end` của câu cuối tình cờ CŨNG là cuối dòng thời gian. Dữ liệu thật
# sau bước đặt lại thời điểm không có hình dạng đó: giữa hai câu là khoảng
# lặng, và sau câu cuối vẫn còn tiếng (im lặng) chạy tiếp tới 20,31s.
MOC_PILOT = [(0.0, 3.216), (6.44, 9.968), (13.88, 16.352)]
DAI_TIENG_PILOT = 20.31


def test_canh_cuoi_phu_HET_tieng_chu_khong_tat_o_chu_cuoi(tmp_path):
    """Đo được 21/09: cảnh cuối chỉ dài 2,472s (đúng bằng clip giọng) trong
    khi tiếng còn chạy tới 20,31s → video 16,35s ghép với tiếng 20,31s.

    `merge_video` không có `-shortest`, nên tệp xuất ra dài bằng TIẾNG: gần 4
    giây cuối **không có hình nào** (đo trên dubbed_video.mp4 của pilot: luồng
    video dừng ở 16,333s còn luồng tiếng chạy tới 20,310s; ffmpeg không rút
    nổi một khung nào ở giây 16,5 / 18 / 20,2).

    Ba cảnh đầu thì đúng — cảnh đổi tại `start` của câu kế nên vẫn khớp lời.
    Sai đúng một chỗ: cảnh CUỐI lấy `end` của câu cuối làm cuối dòng thời
    gian, trong khi mọi cảnh khác lấy `start` của câu kế (tức là tính cả
    khoảng lặng nằm trong cảnh).
    """
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()

    ra = dk.dung_lai_video_theo_giong(
        wd, _segments(MOC_PILOT), dai_tieng=DAI_TIENG_PILOT,
        ghep_video=ghep, do_thoi_luong=lambda _p: DAI_TIENG_PILOT)

    assert ra is not None
    # 6,44 + 7,44 + (20,31 − 13,88)
    assert ghep.goi[-1]["giay"] == pytest.approx([6.44, 7.44, 6.43])


def test_video_dung_lai_KHONG_duoc_ngan_hon_tieng_no_se_ghep_cung(tmp_path):
    """Chốt của test trên, phát biểu theo đúng thứ người xem gặp: tệp xuất ra
    dài bằng TIẾNG, nên hình phải phủ hết chừng ấy giây."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()

    dk.dung_lai_video_theo_giong(
        wd, _segments(MOC_PILOT), dai_tieng=DAI_TIENG_PILOT,
        ghep_video=ghep, do_thoi_luong=lambda _p: DAI_TIENG_PILOT)

    dai_hinh = sum(ghep.goi[-1]["giay"])
    assert dai_hinh >= DAI_TIENG_PILOT - dk.LECH_THOI_LUONG_TOI_DA_S, (
        f"hình chỉ dài {dai_hinh:.2f}s mà tiếng dài {DAI_TIENG_PILOT:.2f}s — "
        f"{DAI_TIENG_PILOT - dai_hinh:.2f} giây cuối không có hình")


def test_tieng_NGAN_hon_cau_cuoi_thi_khong_cat_bot_hinh(tmp_path):
    """Chiều ngược lại: `dai_tieng` chỉ được KÉO DÀI cảnh cuối, không rút.

    Cắt hình ngắn lại theo một con số đo hụt là cắt mất chữ cuối của người ta
    — hỏng nặng hơn hẳn cái đang sửa."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    ghep = _Ghep()

    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), dai_tieng=4.0,
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.0)

    assert ghep.goi[-1]["giay"] == pytest.approx([3.0, 3.0])


def test_KHONG_do_duoc_tieng_thi_giu_nguyen_cach_cu(tmp_path):
    """Không đo được tệp tiếng (`wav_duration_s` trả None) thì vẫn dựng lại
    theo mốc câu — hình lệch dần là lỗi NẶNG hơn một cái đuôi đứng hình, nên
    thà dựng theo cách cũ còn hơn bỏ luôn việc dựng lại."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    ghep = _Ghep()

    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), dai_tieng=None,
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.0)

    assert ghep.goi[-1]["giay"] == pytest.approx([3.0, 3.0])


def test_duong_xuat_DUA_dung_do_dai_tiep_DA_GHEP_cho_D1(tmp_path, monkeypatch):
    """Nối dây: `rebuild_output` phải đưa độ dài tệp tiếng THẬT sang D1.

    Không có phép kiểm này thì hai đầu không gặp nhau: `_moc_that` sửa đúng
    nhưng đường xuất vẫn gọi không kèm số đo, và bản vá chết lặng.

    Đo tệp trên đĩa chứ KHÔNG dùng lại biến `total_duration`: `total_duration`
    là Ý ĐỊNH lúc gọi trộn, thứ sắp được ghép vào video là TỆP.
    """
    import wave

    from autodub import du_an_tu_kich_ban as dk_mod
    from autodub import editor
    from autodub.config import Settings
    from autodub.pipeline import DubPipeline

    def _wav(duong, giay, rate=16000):
        with wave.open(str(duong), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(giay * rate))
        return str(duong)

    wd = tmp_path / "20260921000000_vi"
    (wd / "data" / "segments").mkdir(parents=True)
    (wd / dk.TEN_VIDEO_NGUON).write_bytes(b"video gia")
    # Dòng thời gian ƯỚC LƯỢNG, đúng như `dung_du_an` ghi ra.
    segs = [{"id": i + 1, "text": f"c{i}", "text_vi": f"câu {i}",
             "start": a, "end": b, "duration": round(b - a, 3)}
            for i, (a, b) in enumerate([(0.0, 6.44), (6.44, 13.88),
                                        (13.88, 19.31)])]
    (wd / "data" / "transcript_vi.json").write_text(
        json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    # Giọng THẬT: ngắn hơn ước lượng (số đo pilot).
    for i, giay in enumerate([3.216, 3.528, 2.472], start=1):
        _wav(wd / "data" / "segments" / f"seg_{i:05d}.wav", giay)
    (wd / "data" / "segments" / ".render_mode").write_text(
        DubPipeline.RENDER_MODE, encoding="utf-8")
    _ghi_nguon(str(wd), _anh(tmp_path, 3), giay_chuyen=0.3)

    import autodub.media.audio as audio_mod
    import autodub.media.video as video_mod
    import autodub.text.srt as srt_mod

    def _tron_gia(segments, seg_dir, ra, total_duration, **k):
        # `merge_segments` thật cam kết tệp ra dài ĐÚNG `total_duration`
        # (nền được `apad`/`atrim` về đúng số đó) — dựng lại đúng cam kết ấy.
        return _wav(ra, total_duration)

    monkeypatch.setattr(audio_mod, "merge_segments", _tron_gia)
    monkeypatch.setattr(video_mod, "merge_video", lambda *a, **k: a[2])
    monkeypatch.setattr(srt_mod, "generate_srt", lambda *a, **k: None)

    nhan = {}

    def _d1_gia(work_dir, segments, **kw):
        # Trả None = "không dựng lại" — test này chỉ soi tham số nhận được.
        nhan.update(kw)
        nhan["cuoi_cau_cuoi"] = segments[-1]["end"]

    monkeypatch.setattr(dk_mod, "dung_lai_video_theo_giong", _d1_gia)

    editor.rebuild_output(str(wd), Settings(voice_postprocess=False),
                          bg_mode="none")

    # Câu cuối tắt tiếng ở 16,352s…
    assert nhan["cuoi_cau_cuoi"] == pytest.approx(16.352, abs=0.05)
    # …nhưng tệp tiếng dài tới 20,31s, và D1 phải biết điều đó.
    assert nhan.get("dai_tieng") == pytest.approx(20.31, abs=0.05), (
        "đường xuất không đưa độ dài tệp tiếng sang D1 — cảnh cuối sẽ tắt ở "
        "chữ cuối cùng và đuôi video không có hình")


def test_duong_xuat_CHI_dung_lai_khi_video_dung_la_slideshow():
    """`rebuild_output` là đường xuất CHUNG. Đọc mã nguồn để chắc điều kiện
    còn nguyên — mất nó thì một dự án lồng tiếng thường sẽ bị thay video."""
    import inspect

    from autodub import editor
    ma = inspect.getsource(editor.rebuild_output)
    assert "dung_lai_video_theo_giong" in ma
    assert "os.path.basename(video_path) == TEN_VIDEO_NGUON" in ma, (
        "mất điều kiện này thì video quay thật của người dùng sẽ bị thay bằng "
        "slideshow")


def test_dung_lai_HONG_khong_duoc_giet_luot_xuat():
    """Bản cũ vẫn dùng được, chỉ là hình lệch dần. Nói to rồi đi tiếp."""
    import inspect

    from autodub import editor
    ma = inspect.getsource(editor.rebuild_output)
    i = ma.index("dung_lai_video_theo_giong")
    assert "except Exception" in ma[i:i + 900]


# ================================================================
# I5 — chuyển cảnh phải SỐNG SÓT qua lượt dựng lại theo giọng thật
# ================================================================
#
# Đây là chỗ bản chỉ đạo dễ biến mất nhất mà không ai thấy: người dùng trả
# Vox cho bản chỉ đạo, dựng xong nhìn đúng, rồi D1 dựng LẠI slideshow theo
# giọng thật và ghi đè bằng «Mờ chồng». Video cuối — cái đem đi đăng — không
# còn dấu vết nào của bản chỉ đạo, và không có thông báo nào.

def test_I5_kieu_chuyen_lay_lai_DUNG_bang_luc_dung_lan_dau(tmp_path):
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3), giay_chuyen=0.3,
               kieu_chuyen=["tan", "mo_vong"])
    ghep = _Ghep()
    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 2.5), (2.5, 5.5), (5.5, 7.5)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 7.5)
    assert ghep.goi[-1]["kieu"] == ["tan", "mo_vong"], (
        "dựng lại theo giọng thật đã xoá mất bản chỉ đạo")


def test_I5_du_an_dung_TRUOC_I5_van_mo_lai_duoc(tmp_path):
    """Dự án cũ không có khoá `kieu_chuyen`. «Mờ chồng» đúng là thứ chúng đã
    dựng ra, nên đọc thiếu KHÔNG được đổi hành vi của chúng."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2), giay_chuyen=0.3)   # không có kieu_chuyen
    ghep = _Ghep()
    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.0)
    assert ghep.goi[-1]["kieu"] == "mo_chong"
