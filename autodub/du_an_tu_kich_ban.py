"""Dựng thư mục dự án từ một kịch bản brand — mini-spec H4c.

Từ storyboard (H4a) + danh sách ảnh đã chọn, dựng một thư mục **đúng khuôn dự
án lồng tiếng** để mở thẳng trong Trình chỉnh sửa.

**Vì sao đi đường vòng qua "dự án" thay vì xuất mp4 luôn**: Trình chỉnh sửa
đã có sẵn nghe thử từng câu, sửa lời, đọc lại bằng VieNeu (0 Vox, chạy trên
máy), đổi giọng, ghép xuất. Dựng đúng khuôn thì **không phải làm lại gì cả**.
Và nó giữ đúng Constraint 5 của dự án: luôn cho nghe thử trước khi chốt.

**Trình chỉnh sửa đòi ĐỦ BA thứ** (đọc `editor.load_work_dir`), thiếu một cái
là nó từ chối mở:

1. một **video nguồn** trong thư mục — đây là chỗ dễ hụt nhất, vì kịch bản
   không có video nào sẵn; ta dựng bản trình chiếu ảnh (H4b) làm video nguồn;
2. `data/transcript_vi.json` — mảng segment đã dịch;
3. `securestore` **không khoá** (dự án này không đi qua wizard trả phí nên
   không có gì bị giữ).

Tên tệp video KHÔNG được bắt đầu bằng `dubbed_video`/`retimed_video`/
`slowed_video` — `_find_source_video()` cố ý bỏ qua các tệp đó vì chúng là
sản phẩm phái sinh, không phải nguồn để dựng lại.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from autodub.storyboard import Storyboard, dung_storyboard
from autodub.utils import setup_logging

logger = setup_logging("autodub.du_an_tu_kich_ban")

#: Tên video trình chiếu. Cố ý KHÔNG bắt đầu bằng `dubbed_`/`retimed_`/
#: `slowed_` — ba tiền tố đó bị `_find_source_video()` bỏ qua, và dự án sẽ
#: không mở được với một lỗi chẳng liên quan gì tới nguyên nhân thật.
TEN_VIDEO_NGUON = "storyboard_video.mp4"

#: Ghi lại nguồn gốc dự án để về sau còn truy được kịch bản/blueprint nào đẻ
#: ra nó. Không có thì một thư mục dự án là một hộp đen.
TEN_NGUON_GOC = "nguon_kich_ban.json"


#: Lệch thời lượng tối đa cho phép giữa video dựng ra và dòng thời gian ghi
#: trong transcript — mini-spec H4c-1.
#:
#: Con số này **đo được, không chọn bừa**. Sau khi bù phần chuyển cảnh, dựng
#: thật bằng ffmpeg trên 8 hình dạng kịch bản khác nhau (2→9 ảnh, 0,34→11,9
#: giây mỗi ảnh, tổng 0,68→35,2 giây) cho lệch tối đa **đúng 1 khung ở 30fps
#: = 0,0333s**, và lệch đó **KHÔNG tăng** theo số ảnh hay độ dài video — nó
#: là lượng tử hoá khung hình, tức sàn của thứ 30fps làm được.
#:
#: Lấy 2 khung để chừa chỗ cho máy khác/bản ffmpeg khác, vẫn nhỏ hơn 9 lần
#: sai lệch cũ của một video 3 đoạn (0,6s) và không tăng theo độ dài.
LECH_THOI_LUONG_TOI_DA_S = 2 / 30


def _do_thoi_luong_that(duong_video: str) -> float | None:
    """Đo thời lượng video bằng ffprobe. None nếu không đọc được."""
    from autodub.media.video import probe_duration_s

    return probe_duration_s(duong_video)


class ThieuAnh(RuntimeError):
    """Có đoạn chưa được gán ảnh.

    KHÔNG tự sinh ảnh thay người dùng (Guardrail 4 của H4): sinh ảnh tốn 33
    Vox mỗi tấm, tự bấm hộ là tiêu tiền của người ta mà không xin phép.
    """


class VideoLechThoiLuong(RuntimeError):
    """Video dựng ra không khớp dòng thời gian của transcript.

    Vì sao phải NÉM chứ không chỉ cảnh báo: transcript là thứ Trình chỉnh sửa
    dùng để cắt giọng đọc cho từng đoạn. Video ngắn hơn transcript nghĩa là
    hình đổi sớm dần so với tiếng, và sai lệch **cộng dồn** về cuối video —
    người dùng sẽ nghe thử thấy "hơi lệch" ở giữa rồi lệch hẳn ở cuối mà
    không hiểu vì sao. Dựng tiếp một dự án như vậy là đặt mọi bước sau lên
    một dòng thời gian sai.
    """


@dataclass
class KetQuaDungDuAn:
    work_dir: str
    storyboard: Storyboard
    duong_video: str
    duong_transcript: str


def _segment_tu_doan(doan, thu_tu: int) -> dict:
    """Một segment đúng khuôn Trình chỉnh sửa đọc được.

    `text_vi` là lời ĐỌC (Trình chỉnh sửa đưa nó cho TTS), `sub_vi` là chữ
    hiện trên hình — hai thứ khác nhau và cố ý tách: caption gợi ý của kịch
    bản ngắn gọn để đọc bằng mắt, còn lời đọc là câu nói đầy đủ.
    """
    return {
        "id": thu_tu,
        "start": round(doan.bat_dau_s, 3),
        "end": round(doan.ket_thuc_s, 3),
        "duration": round(doan.giay, 3),
        "text": doan.loi_doc,
        "text_vi": doan.loi_doc,
        "sub_vi": doan.caption or doan.loi_doc,
    }


class AnhAiChuaDat(RuntimeError):
    """Có ảnh do AI vẽ không qua được phép kiểm tuân thủ — RS-16.

    KHÁC `ThieuAnh` (chưa chọn ảnh) và khác `KichBanChuaDungDuoc` (kịch bản
    chưa duyệt): ở đây ảnh CÓ, kịch bản SẠCH, nhưng tấm ảnh không được phép
    đi vào một video đem bán.
    """


#: Từ vựng phán quyết của H4d ↔ của C1. Hai mini-spec, hai bộ chữ, cùng một
#: ý nghĩa "ảnh này dùng để bán được".
#:
#: `story_image.kiem_anh` trả "DAT"/"CO_SAN_PHAM"; `product_video.AnhNguon`
#: đọc "SAFE". Ánh xạ phải VIẾT RA, không được để ngầm: dịch ẩu theo một
#: chiều thì chặn sạch mọi ảnh, theo chiều kia thì mở toang cổng — và cả hai
#: đều im lặng.
_PHAN_QUYET_SANG_KET_LUAN = {"DAT": "SAFE"}


def _anh_nguon_tu_ai(duong_dan: str, mo_ta: dict):
    """Đổi bản ghi ảnh AI của H4d thành `AnhNguon` mà cổng C1 đọc được."""
    from autodub.product_video import AnhNguon

    phan_quyet = str(mo_ta.get("phan_quyet") or "")
    return AnhNguon(
        duong_dan=duong_dan,
        boi_canh=str(mo_ta.get("goi_y") or ""),
        # Phán quyết KHÔNG nằm trong bảng ánh xạ thì giữ nguyên chuỗi gốc —
        # nó sẽ không khớp "SAFE" và bị chặn. Đó là hướng an toàn: một mã
        # phán quyết lạ nghĩa là bản H4d mới thêm trạng thái mà cổng này chưa
        # biết, và "chưa biết" phải là "không cho qua".
        ket_luan=_PHAN_QUYET_SANG_KET_LUAN.get(phan_quyet, phan_quyet),
        ly_do=str(mo_ta.get("ly_do") or ""),
        da_kiem=bool(mo_ta.get("da_kiem")),
        da_dong_nhan=bool(mo_ta.get("da_dong_nhan")),
        bam_luc_kiem=str(mo_ta.get("bam") or ""),
    )


#: Mốc lệch dưới ngưỡng này thì KHÔNG dựng lại — chốt "đừng sửa quá tay".
#:
#: Dựng lại tốn hàng chục giây ffmpeg, và thay một tệp đang đúng bằng một tệp
#: cũng đúng là rủi ro không đổi lại được gì. 0,25 giây là dưới ngưỡng người
#: xem nhận ra hình lệch lời.
NGUONG_DANG_DUNG_LAI_S = 0.25


def _moc_that(segments: list[dict],
              dai_tieng: float | None = None) -> list[float] | None:
    """Thời lượng từng cảnh, suy từ mốc THẬT của các câu — D1.

    ``segments`` ở đây đã đi qua bước đặt lại thời điểm, nên ``start``/``end``
    là vị trí người nghe sẽ nghe thật, không còn là ước lượng.

    ``dai_tieng`` là thời lượng ĐO ĐƯỢC của tệp tiếng sắp ghép cùng. Cảnh cuối
    phải kéo tới hết tệp ấy, vì **cuối câu cuối KHÔNG phải cuối dòng thời
    gian**: mọi cảnh khác dài tới ``start`` của câu kế (tức là ôm trọn khoảng
    lặng nằm trong cảnh), còn cảnh cuối thì không có câu kế để dựa vào. Lấy
    ``end`` của câu cuối làm mốc kết nghĩa là cắt hình ngay khi tiếng nói tắt,
    trong khi tệp tiếng vẫn còn chạy.

    Đo được 21/09 (pilot H4): câu cuối tắt tiếng ở 16,352s còn
    ``audio_vi_full.wav`` dài 20,31s — `merge_video` không có ``-shortest`` nên
    tệp xuất ra dài bằng TIẾNG, và **3,96 giây cuối không có khung hình nào**.

    Trả ``None`` khi không lát kín được dòng thời gian (câu chồng nhau, hoặc
    mốc không tăng dần) — lúc đó giữ nguyên video cũ chứ không đoán.
    """
    if len(segments) < 1:
        return None
    moc = [float(s.get("start") or 0.0) for s in segments]
    cuoi = float(segments[-1].get("end") or 0.0)
    if dai_tieng is not None:
        # CHỈ kéo dài, không bao giờ rút: một số đo hụt mà rút hình lại thì
        # cắt mất chữ cuối của người ta — hỏng nặng hơn hẳn cái đang sửa.
        cuoi = max(cuoi, float(dai_tieng))
    giay = [moc[i + 1] - moc[i] for i in range(len(moc) - 1)] + [cuoi - moc[-1]]
    if any(g <= 0 for g in giay):
        return None
    return giay


def dung_lai_video_theo_giong(
    work_dir: str, segments: list[dict], *,
    dai_tieng: float | None = None,
    ghep_video=None, do_thoi_luong=None,
) -> str | None:
    """Dựng lại slideshow theo GIỌNG ĐỌC THẬT — D1. 0 Vox.

    Trả về đường dẫn video vừa dựng, hoặc ``None`` khi **cố ý không làm gì**.

    Vì sao cần: `dung_du_an()` dựng hình theo ƯỚC LƯỢNG thời gian đọc. Giọng
    thật lệch ~5% (đo pilot H4: 19,30s so với 20,31s), và vì các đoạn kịch bản
    nối liền nhau **không có khoảng lặng nào để dồn trễ**, phần lệch ấy cộng
    dồn: càng về cuối hình càng chạy trước lời.

    Engine vốn xử lý chuyện này bằng cách **nén giọng đọc** cho vừa chỗ
    (`timing_max_atempo`). Với video quay thì đúng. Với slideshow thì ngược
    mới đúng: ảnh tĩnh KHÔNG có nhịp riêng, giữ 2,0 hay 2,3 giây đều không ai
    nhận ra — ép giọng đọc nhanh lên để vừa một tấm ảnh tĩnh là hy sinh đúng
    thứ người xem nghe được.

    ``dai_tieng`` — thời lượng ĐO ĐƯỢC của tệp tiếng sắp ghép cùng (bên gọi đo
    tệp trên đĩa, không đưa con số dự định). Hình phải phủ hết chừng ấy giây:
    ``merge_video`` không có ``-shortest`` nên tệp xuất ra luôn dài bằng tiếng,
    hình ngắn hơn là đuôi video không có khung nào. Xem `_moc_that`.

    **Mọi nhánh trả ``None`` đều là cố ý.** Hàm này được gọi từ đường xuất
    CHUNG của mọi dự án, nên nghi ngờ gì thì giữ nguyên hành vi cũ.
    """
    duong_video = os.path.join(work_dir, TEN_VIDEO_NGUON)
    from autodub.workdir import data_path

    duong_nguon = data_path(work_dir, TEN_NGUON_GOC)
    if not os.path.isfile(duong_nguon):
        return None                     # không phải dự án dựng từ kịch bản
    try:
        with open(duong_nguon, encoding="utf-8") as f:
            nguon = json.load(f)
    except (ValueError, OSError) as e:
        logger.warning("D1: không đọc được %s (%s) — giữ nguyên video cũ",
                       duong_nguon, e)
        return None

    anh = [str(a or "") for a in (nguon.get("anh_moi_doan") or [])]
    if not anh:
        # Dự án dựng bằng bản CŨ hơn D1: không có danh sách ảnh nào để dựng
        # lại. Không phải lỗi — chỉ là không làm được.
        return None
    if len(anh) != len(segments):
        logger.warning(
            "D1: dự án có %d ảnh nhưng %d câu — kịch bản đã đổi số câu, "
            "giữ nguyên video cũ", len(anh), len(segments))
        return None
    thieu = [a for a in anh if not os.path.isfile(a)]
    if thieu:
        logger.warning(
            "D1: %d tệp ảnh không còn ở chỗ cũ (vd %s) — giữ nguyên video cũ",
            len(thieu), thieu[0])
        return None

    giay = _moc_that(segments, dai_tieng)
    if giay is None:
        logger.warning("D1: mốc các câu không lát kín được dòng thời gian "
                       "(câu chồng nhau?) — giữ nguyên video cũ")
        return None

    # "Đừng sửa quá tay": ước lượng đã đúng sẵn thì đừng dựng lại. Đo CHÍNH
    # video đang có chứ không so với con số ghi trong tệp truy nguồn — tệp ghi
    # ý ĐỊNH lúc dựng, còn thứ người xem gặp là tệp trên đĩa.
    do = do_thoi_luong or _do_thoi_luong_that
    hien_co = do(duong_video) if os.path.isfile(duong_video) else None
    if hien_co is not None and abs(hien_co - sum(giay)) <= NGUONG_DANG_DUNG_LAI_S:
        logger.info("D1: giọng thật khớp ước lượng (lệch %.2f giây) — "
                    "không dựng lại", abs(hien_co - sum(giay)))
        return None

    if ghep_video is None:
        from autodub.product_video import ghep_anh_nguoi_dung
        ghep_video = ghep_anh_nguoi_dung
    giay_chuyen = float(nguon.get("giay_chuyen") or 0.0)
    ghep_video(list(anh), duong_video, giay_moi_anh=giay,
               giay_chuyen=giay_chuyen)

    # Cổng thời lượng H4c-1 vẫn áp dụng — dựng lại mà lệch thì phải hỏng TO
    # TIẾNG, không âm thầm ghi đè một video sai lên một video đúng.
    thuc_te = do(duong_video)
    if thuc_te is None or abs(thuc_te - sum(giay)) > LECH_THOI_LUONG_TOI_DA_S:
        raise VideoLechThoiLuong(
            f"Dựng lại hình theo giọng đọc thật nhưng video ra "
            f"{thuc_te if thuc_te is not None else float('nan'):.2f} giây "
            f"trong khi lời đọc dài {sum(giay):.2f} giây. Giữ bản cũ thì hình "
            "lệch dần so với tiếng; dựng tiếp bản này còn lệch hơn.")

    logger.info("D1: đã dựng lại hình theo giọng thật — %d cảnh, %.1f giây",
                len(giay), sum(giay))
    return duong_video


def dung_du_an(
    kich_ban: dict, anh_moi_doan: list[str], work_dir: str, *,
    blueprint: dict | None = None, giay_chuyen: float = 0.3,
    anh_ai: dict | None = None,
    ghep_video=None, do_thoi_luong=None,
) -> KetQuaDungDuAn:
    """Dựng thư mục dự án mở được trong Trình chỉnh sửa.

    ``kich_ban``: BrandScript ĐÃ `ready` — `dung_storyboard()` tự chặn nếu
    chưa, không cần kiểm lại ở đây (một chỗ chặn là đủ, hai chỗ thì có ngày
    lệch nhau).

    ``anh_moi_doan``: đường dẫn ảnh cho TỪNG đoạn, đúng thứ tự. Thiếu ảnh cho
    bất kỳ đoạn nào ⇒ :class:`ThieuAnh` — không tự sinh thay người dùng.

    ``ghep_video``: tiêm vào để test không phải chạy ffmpeg thật. Mặc định
    dùng `product_video.ghep_anh_nguoi_dung()` — KHÔNG phải cổng ảnh AI của
    C1, xem chú thích ở chỗ gọi.
    """
    board = dung_storyboard(kich_ban, blueprint)

    thieu = [i + 1 for i, a in enumerate(anh_moi_doan) if not str(a or "").strip()]
    if len(anh_moi_doan) != len(board.doan) or thieu:
        con_lai = thieu or list(range(len(anh_moi_doan) + 1, len(board.doan) + 1))
        raise ThieuAnh(
            f"Chưa có ảnh cho đoạn {', '.join(str(i) for i in con_lai)}. "
            "Chọn ảnh cho đủ mọi đoạn rồi dựng lại.")

    os.makedirs(work_dir, exist_ok=True)
    duong_video = os.path.join(work_dir, TEN_VIDEO_NGUON)

    # Thời lượng RIÊNG từng ảnh, lấy thẳng từ storyboard (H4b) — chia đều thì
    # đoạn hook ngắn và đoạn bằng chứng dài giữ hình bằng nhau.
    # --- RS-16: ảnh do AI vẽ phải qua ĐỦ ba phép kiểm -------------------
    #
    # Chú thích trong `product_video.dung_video_tu_anh_nguoi_dung` đã cảnh báo
    # từ trước khi H4d tồn tại: "Khi H4d thêm đường sinh ảnh AI: ảnh sinh ra
    # KHÔNG được đi qua hàm này." Nhưng H4d lên rồi mà cổng thì chưa — giao
    # diện chỉ giữ ĐƯỜNG DẪN ảnh, vứt phán quyết và dấu băm, nên
    # `kiem_lai_truoc_khi_xuat()` không có gì để chạy.
    #
    # Đặt ở ĐÂY chứ không ở giao diện, vì đây là hàm duy nhất tạo ra tệp video
    # từ kịch bản — nó phải là chỗ cuối cùng nói được "không". Cổng ở giao
    # diện thì mọi lối gọi khác (test, script, bản sau) đều đi vòng qua được.
    #
    # Kiểm LẠI tại đây chứ không tin cờ đã lưu: giữa lúc vẽ xong và lúc dựng
    # có thể là vài ngày, và `kiem_lai_truoc_khi_xuat` so lại BĂM của tệp —
    # tệp bị sửa sau khi kiểm thì nội dung không còn là tấm đã được duyệt.
    if anh_ai:
        from autodub.product_video import kiem_lai_truoc_khi_xuat

        can_kiem = [_anh_nguon_tu_ai(anh_moi_doan[i], mo_ta)
                    for i, mo_ta in sorted(anh_ai.items())
                    if 0 <= i < len(anh_moi_doan)]
        if can_kiem:
            kq = kiem_lai_truoc_khi_xuat(can_kiem)
            if not kq.cho_phep:
                chi_tiet = "; ".join(f"{t}: {l}" for t, l in kq.bi_chan)
                raise AnhAiChuaDat(
                    "Có ảnh do AI vẽ chưa dùng để bán được — " + chi_tiet
                    + ". Vẽ lại ảnh đó, hoặc chọn ảnh bạn tự chụp cho đoạn ấy.")

    giay = [d.giay for d in board.doan]
    if ghep_video is None:
        # `ghep_anh_nguoi_dung` chứ KHÔNG phải `dung_video`: hàm sau bắt mọi
        # ảnh phải qua kiểm bao bì và đã đóng nhãn AI-generated LÊN ẢNH — ba
        # phép kiểm dựng cho ảnh do AI vẽ (C1). Ảnh người dùng tự chụp không
        # thuộc diện đó, và điền các cờ ấy cho nó chỉ để qua cổng là bịa
        # trạng thái tuân thủ. Nhãn AI trên VIDEO thì vẫn được đóng (kịch bản
        # do mô hình viết, giọng đọc là giọng tổng hợp).
        from autodub.product_video import ghep_anh_nguoi_dung

        ghep_video = ghep_anh_nguoi_dung
    ghep_video(list(anh_moi_doan), duong_video, giay_moi_anh=giay,
               giay_chuyen=giay_chuyen)

    # --- Cổng thời lượng (H4c-1) ------------------------------------------
    # ĐO LẠI video vừa dựng, không tin lệnh ffmpeg đã chạy xong là đúng.
    #
    # Đây là chỗ lỗi cũ lọt qua: `xfade` chồng cảnh nên ăn mất `giay_chuyen`
    # mỗi lần chuyển, video ra ngắn hơn transcript đúng `giay_chuyen × (n-1)`
    # — mà transcript thì vẫn ghi mốc cộng dồn đầy đủ. Không ai đo nên không
    # ai biết, và người dùng chỉ gặp nó ở bước nghe thử: hình đổi sớm dần,
    # lệch hẳn về cuối.
    tong_mong_muon = sum(giay)
    do = do_thoi_luong or _do_thoi_luong_that
    thuc_te = do(duong_video)
    if thuc_te is None:
        raise VideoLechThoiLuong(
            "Không đọc được thời lượng video vừa dựng để đối chiếu. Dự án "
            "chưa dựng xong — thiếu phép đối chiếu này thì hình có thể lệch "
            "dần so với tiếng mà không có dấu hiệu nào.")
    lech = abs(thuc_te - tong_mong_muon)
    if lech > LECH_THOI_LUONG_TOI_DA_S:
        raise VideoLechThoiLuong(
            f"Video dựng ra dài {thuc_te:.2f} giây nhưng dòng thời gian của "
            f"kịch bản là {tong_mong_muon:.2f} giây (lệch {lech:.2f} giây). "
            "Dựng tiếp thì hình sẽ lệch dần so với lời đọc và càng về cuối "
            "càng lệch. Thử lại với kiểu chuyển cảnh «cắt thẳng», hoặc báo "
            "lỗi kèm số giây ở trên.")

    from autodub.workdir import data_path

    # Khai luôn CƠ CHẾ ĐỌC của dự án này — tìm ra bằng pilot H4 cục bộ 11/09.
    #
    # `editor._check_render_mode()` chặn xuất khi thư mục `segments/` có tệp
    # .wav mà không có dấu `.render_mode` khớp `DubPipeline.RENDER_MODE`; nó
    # đang canh những dự án đời cũ đọc theo cơ chế gộp câu. Dấu đó do
    # `DubPipeline` ghi — mà dự án dựng từ kịch bản **không đi qua pipeline**
    # lần nào, nên nó không bao giờ có dấu.
    #
    # Hậu quả: người dùng dựng dự án, đọc bằng VieNeu, bấm Xuất, rồi nhận
    # "Thư mục này chứa giọng đọc tạo theo cơ chế gộp câu đời cũ. Hãy chạy
    # tiếp dự án một lần…" — một việc **không tồn tại** cho loại dự án này.
    # Câu báo lỗi đúng với ca nó canh, nhưng chỉ sai đường hoàn toàn ở đây.
    #
    # Dự án này đọc theo TỪNG CÂU ngay từ đầu, nên khai đúng như vậy.
    from autodub.pipeline import DubPipeline

    dau = data_path(work_dir, os.path.join("segments", ".render_mode"),
                    create_dir=True)
    os.makedirs(os.path.dirname(dau), exist_ok=True)
    with open(dau, "w", encoding="utf-8") as f:
        f.write(f"{DubPipeline.RENDER_MODE}\n")

    duong_transcript = data_path(work_dir, "transcript_vi.json", create_dir=True)
    segments = [_segment_tu_doan(d, i + 1) for i, d in enumerate(board.doan)]
    with open(duong_transcript, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=1)

    # Truy nguồn: thư mục dự án không có cái này là một hộp đen — về sau
    # không biết kịch bản nào, brand nào, video tham khảo nào đẻ ra nó.
    with open(data_path(work_dir, TEN_NGUON_GOC, create_dir=True),
              "w", encoding="utf-8") as f:
        json.dump({
            "brand_script_id": kich_ban.get("id", ""),
            "flow_blueprint_id": kich_ban.get("flowBlueprintId", ""),
            "brand_profile_id": kich_ban.get("brandProfileId", ""),
            "originality_check_version": kich_ban.get("originalityCheckVersion", 0),
            "so_doan": len(board.doan),
            "tong_giay_uoc_luong": board.tong_giay,
            "canh_bao": board.canh_bao,
            # D1 — GIỮ LẠI danh sách ảnh. Trước đây hàm này dựng video xong
            # rồi vứt danh sách đi, nên về sau không còn gì để dựng lại khi
            # đã biết giọng đọc thật dài bao nhiêu.
            "anh_moi_doan": list(anh_moi_doan),
            "giay_chuyen": giay_chuyen,
        }, f, ensure_ascii=False, indent=1)

    logger.info("Đã dựng dự án %s: %d đoạn, ước %.1f giây",
                work_dir, len(board.doan), board.tong_giay)
    return KetQuaDungDuAn(work_dir=work_dir, storyboard=board,
                          duong_video=duong_video,
                          duong_transcript=duong_transcript)
