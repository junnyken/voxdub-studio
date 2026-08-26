"""V97 phần 1 — gộp mẩu vụn TRƯỚC khi tính tiền.

Máy chủ tính tiền theo SỐ DÒNG (10 Vox nền + 2 Vox dịch mỗi dòng), mà bộ nghe
cắt theo khoảng lặng 500ms nên một câu liền mạch có thể vỡ thành hàng chục mẩu
một-hai chữ. Trước mini-spec này, luồng lồng tiếng gửi thẳng các mẩu đó đi
dịch — trả tiền cho từng mẩu.

Ba điều bộ test này giữ, đều là chỗ `gop_cau` (bản dùng cho .txt) làm KHÔNG
đủ cho luồng lồng tiếng:

1. Giữ nguyên `id` và mọi trường khác — `id` là tên tệp WAV của từng câu.
2. Không bao giờ gộp hai người nói thành một dòng.
3. Hạn mức chặt hơn bản .txt, vì những dòng này còn phải làm phụ đề.
"""
from __future__ import annotations

from autodub.transcribe_tool import (GOP_DICH_TOI_DA_CHU, GOP_DICH_TOI_DA_GIAY,
                                     gop_cau, gop_de_dich)


def _mau(*bo) -> list[dict]:
    """(id, start, end, text[, người nói]) → danh sách segment.

    Dùng ĐÚNG tên trường mà `diarization.assign_speakers()` ghi ra
    (`speaker_label`). Bản đầu của tệp này dựng dữ liệu giả bằng trường
    `speaker` — một tên không hề tồn tại trên mẩu ASR — nên test xanh trong
    khi mã thật gộp nhầm hai người thành một dòng. Bài học: dữ liệu giả sai
    tên trường là test không kiểm gì cả.
    """
    ra = []
    for x in bo:
        seg = {"id": x[0], "start": x[1], "end": x[2], "text": x[3]}
        if len(x) > 4:
            seg["speaker_label"] = x[4]
        ra.append(seg)
    return ra


def test_gop_cac_mau_vun_lien_nhau():
    segs = _mau((1, 0.0, 0.8, "Hôm nay"), (2, 0.9, 1.6, "chúng ta"),
                (3, 1.7, 2.4, "học bài mới."))
    ra = gop_de_dich(segs)
    assert len(ra) == 1
    assert ra[0]["text"] == "Hôm nay chúng ta học bài mới."
    assert (ra[0]["start"], ra[0]["end"]) == (0.0, 2.4)


def test_giu_id_cua_mau_dau():
    """`id` là tên tệp WAV từng câu (seg_wav_path) — đánh số lại là trỏ nhầm
    tệp của lần chạy trước."""
    ra = gop_de_dich(_mau((7, 0.0, 0.8, "Xin"), (8, 0.9, 1.5, "chào.")))
    assert ra[0]["id"] == 7


def test_khong_gop_qua_hai_nguoi_noi():
    """Gộp hai người thành một dòng là giao nhầm giọng cho cả đoạn."""
    segs = _mau((1, 0.0, 0.8, "Anh khỏe", "A"), (2, 0.9, 1.5, "không", "A"),
                (3, 1.6, 2.2, "Tôi khỏe", "B"))
    ra = gop_de_dich(segs)
    assert len(ra) == 2
    assert ra[0]["speaker_label"] == "A" and ra[1]["speaker_label"] == "B"
    assert ra[1]["text"] == "Tôi khỏe"


def test_giu_moi_truong_khac():
    segs = [{"id": 1, "start": 0.0, "end": 0.8, "text": "Xin",
             "style": "vui", "no_speech_prob": 0.01},
            {"id": 2, "start": 0.9, "end": 1.5, "text": "chào."}]
    ra = gop_de_dich(segs)
    assert ra[0]["style"] == "vui"
    assert ra[0]["no_speech_prob"] == 0.01


def test_noi_ca_moc_tung_chu():
    """`words` của mẩu đầu là danh sách CỤT nếu chỉ giữ lại nó."""
    segs = [{"id": 1, "start": 0.0, "end": 0.8, "text": "Xin",
             "words": [{"word": "Xin", "start": 0.0, "end": 0.8}]},
            {"id": 2, "start": 0.9, "end": 1.5, "text": "chào.",
             "words": [{"word": "chào.", "start": 0.9, "end": 1.5}]}]
    ra = gop_de_dich(segs)
    assert [w["word"] for w in ra[0]["words"]] == ["Xin", "chào."]


def test_nghi_lau_thi_tach_dong():
    segs = _mau((1, 0.0, 0.8, "Hết ý này"), (2, 5.0, 5.8, "sang ý khác"))
    assert len(gop_de_dich(segs)) == 2


def test_han_muc_chat_hon_ban_txt():
    """Dòng của luồng lồng tiếng còn phải làm phụ đề đọc được — 14 giây/220
    chữ của bản .txt là quá dài để hiển thị."""
    assert GOP_DICH_TOI_DA_GIAY < 14.0
    assert GOP_DICH_TOI_DA_CHU < 220
    # Cùng một chuỗi mẩu: bản .txt gộp thành ít dòng hơn bản lồng tiếng.
    segs = [{"id": i, "start": i * 0.9, "end": i * 0.9 + 0.8,
             "text": "chữ đệm dài dòng"} for i in range(20)]
    assert len(gop_de_dich(segs)) > len(gop_cau(segs))


def test_gop_lai_lan_nua_khong_doi():
    """Chạy tiếp sẽ nạp bản đã gộp rồi gộp lần nữa — phải đứng yên, nếu không
    mỗi lần chạy lại là mốc thời gian lại trôi."""
    segs = [{"id": i, "start": i * 0.9, "end": i * 0.9 + 0.8,
             "text": f"mẩu {i}"} for i in range(30)]
    mot_lan = gop_de_dich(segs)
    assert gop_de_dich(mot_lan) == mot_lan


def test_bo_mau_rong():
    segs = _mau((1, 0.0, 0.8, "Xin"), (2, 0.9, 1.0, "   "), (3, 1.1, 1.5, "chào."))
    ra = gop_de_dich(segs)
    assert ra[0]["text"] == "Xin chào."


def test_tiet_kiem_that_tren_du_lieu_vun():
    """Đo đúng thứ người dùng phải trả: số dòng bị tính tiền."""
    segs = [{"id": i, "start": i * 1.6, "end": i * 1.6 + 1.2, "text": "hai chữ"}
            for i in range(300)]
    truoc, sau = len(segs), len(gop_de_dich(segs))
    assert sau < truoc / 2, f"gộp xong vẫn còn {sau}/{truoc} dòng"


def test_ten_truong_nguoi_noi_khop_tang_phan_giong_that():
    """Chốt chống lặp lại lỗi gốc: `gop_de_dich` phải đọc đúng tên trường mà
    `assign_speakers()` ghi ra. Sai tên là gộp nhầm hai người, và test dùng
    dữ liệu giả cùng tên sai sẽ không bắt được."""
    import ast

    nguon = open("autodub/speech/diarization.py", encoding="utf-8").read()
    assert 'seg["speaker_label"] = best_speaker' in nguon, \
        "tầng phân giọng đổi tên trường — cập nhật _ai_noi cho khớp"

    tt = open("autodub/transcribe_tool.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(tt)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_ai_noi":
            than = ast.get_source_segment(tt, nut) or ""
            break
    else:
        raise AssertionError("không còn hàm _ai_noi")
    assert "speaker_label" in than, "hàm gộp không đọc nhãn người nói thật"
    assert "voice" in than, "hai mẩu khác giọng vẫn có thể bị nối làm một"


def test_khong_gop_hai_mau_khac_giong_du_cung_nhan():
    """Giọng đã gán khác nhau thì nối lại chỉ đọc được một giọng."""
    segs = [{"id": 1, "start": 0.0, "end": 0.8, "text": "Xin",
             "speaker_label": "A", "voice": "Giọng 1"},
            {"id": 2, "start": 0.9, "end": 1.5, "text": "chào",
             "speaker_label": "A", "voice": "Giọng 2"}]
    assert len(gop_de_dich(segs)) == 2
