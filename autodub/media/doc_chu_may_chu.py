"""Đọc lại chữ overlay bằng mô hình nhìn ảnh trên máy chủ — mini-spec H2b
(09/09/2026).

**Vì sao cần**: bộ OCR chạy trên máy (RapidOCR, model bundled
``ch_PP-OCRv4_rec_infer.onnx``) có từ điển đầu ra 6.623 ký tự mà CHỈ 2 ký tự
thuộc bộ tiếng Việt có dấu (``É``, ``Ó``). Các chữ ``ă â đ ê ô ơ ư`` và mọi
dấu thanh KHÔNG nằm trong từ điển, nên model không thể phát ra chúng — dù ảnh
nét tới đâu, dù chỉnh tham số gì. Đo thật 09/09 trên khung hình video nén:
"Đăng ký kênh để không bỏ lỡ video mới!" đọc ra "Dang ky kenh de khong bo lo
video moi", **confidence vẫn 0,84-0,99**.

**Vì sao không chỉ đổi model OCR**: các từ điển thay thế đều không đủ —
``latin_dict`` của PaddleOCR thiếu 102/134 ký tự Việt, ``ppocrv5_latin_dict``
thiếu 90/134, ``vi_dict`` đủ chữ thường nhưng thiếu 66 chữ HOA có dấu.
PaddlePaddle không phát hành model nhận dạng tiếng Việt chính thức. Đo thêm:
Tesseract ``vie`` (nhẹ, 1,5 MB) ra dấu thật nhưng chỉ đúng ~87% và còn nhiễu
ký tự; VietOCR đúng hơn nhưng kéo theo 1,5 GB PyTorch + trọng số 151,8 MB tải
từ một tên miền cá nhân (đo được 60 KB/s ⇒ ~42 phút) nên không hợp cho bản
``.exe`` gửi người dùng cuối.

**Nguyên tắc quan trọng nhất của module này — KHÔNG gửi mọi khung hình lên
máy chủ.** RapidOCR đọc mất dấu nhưng vẫn phân biệt rất tốt "khung này có chữ
KHÁC khung trước", vì phần phụ âm/chữ số vẫn đúng. Nên: dùng RapidOCR (miễn
phí, tại máy) để chia các khung thành từng ĐOẠN chữ giống nhau, rồi chỉ gửi
MỘT khung đại diện cho mỗi đoạn, và áp kết quả đọc đúng cho cả đoạn. Video 60
giây lấy mẫu thích ứng ra ~152 khung nhưng thường chỉ có ~15 caption khác
nhau — tiết kiệm khoảng 10 lần cả tiền lẫn thời gian.
"""
from __future__ import annotations

import logging
from dataclasses import replace

logger = logging.getLogger(__name__)

#: Số khung gửi trong MỘT lượt gọi. Bằng đúng `soAnhToiDa` của tác vụ
#: `doc_chu_khung_hinh` phía máy chủ VÀ trần `images.maxItems` của route
#: `/v1/ai/assist` — gửi quá là bị chặn ở tầng schema với một lỗi trống không.
SO_KHUNG_MOI_LUOT = 6

#: Giá một lô, khớp `credit.cost.assist.doc_chu_khung_hinh` ở máy chủ. Để ở
#: đây để nhật ký nói được số tiền thật; `tests/test_gia_doc_chu_trung_thuc.py`
#: chốt hai bên không lệch nhau.
VOX_MOI_LO = 8

#: Vượt mức này thì HỎI trước khi tiêu. Lượt chạy thật 11/09/2026 trên một
#: video 34 giây tốn 88 Vox rồi hỏng ở bước cuối — người dùng không có chỗ
#: nào để can thiệp, và màn hình lúc đó hứa "khoảng 32 Vox".
#:
#: Không hỏi mọi lượt: hỏi cả những lượt 16 Vox là dạy người dùng bấm Đồng ý
#: theo phản xạ, rồi lượt 88 Vox cũng trôi qua y như vậy.
NGUONG_XIN_PHEP_VOX = 50

#: Cạnh dài tối đa của khung hình gửi đi. Đo thật 09/09: thu nhỏ về 640px vẫn
#: đọc đúng 100% trên khung hình video nén, mà nhẹ hơn hẳn ảnh gốc (0,7 MB
#: PNG → ~60 KB JPEG). Trần tổng dung lượng ảnh của máy chủ là thật, không
#: phải lý thuyết: gửi 6 ảnh gốc là chạm trần và bị trả 413.
CANH_DAI_TOI_DA = 640


#: Hai khung liền nhau giống nhau BAO NHIÊU thì coi là cùng một caption.
#:
#: `_khoa_doan` vốn so chuỗi NGUYÊN VĂN. RapidOCR trên chữ tiếng Việt nhiễu
#: nên cùng một caption đọc ở hai khung liền nhau ra khác vài ký tự, và mỗi
#: khung thành một đoạn riêng — mỗi đoạn thừa là một khung nữa gửi lên máy
#: chủ, tức 8 Vox mỗi sáu khung.
#:
#: Đo trên dữ liệu THẬT chủ dự án gửi 12/09 (`ocr_chan_doan.json`, 104 mốc
#: lấy mẫu, 65 đoạn):
#:
#:     giống >= 75%: 65 -> 31 đoạn = 6 lô = 48 Vox
#:     giống >= 80%: 65 -> 33 đoạn = 6 lô = 48 Vox   <- chọn
#:     giống >= 85%: 65 -> 34 đoạn = 6 lô = 48 Vox
#:     giống >= 90%: 65 -> 40 đoạn = 7 lô = 56 Vox
#:     giống >= 95%: 65 -> 47 đoạn = 8 lô = 64 Vox
#:
#: 75–85% là một CAO NGUYÊN (đều 48 Vox) — lấy 80% ở giữa, không đứng sát
#: mép. Ở mức đó, soi tay cả 17 nhóm gộp được: KHÔNG nhóm nào gộp nhầm hai
#: caption khác nhau, tất cả đều là cùng một caption đọc lệch.
#:
#: 88 Vox -> 48 Vox, giảm 45%.
NGUONG_GIONG_DE_GOP = 0.80

#: Chuỗi ngắn hơn mức này thì đòi giống HỆT — hai chuỗi ba ký tự rất dễ đạt
#: tỉ lệ giống cao một cách tình cờ (`roa` vs `rob` = 67%, nhưng `abc` vs
#: `abd` = 67% cũng vậy). Dưới ngưỡng này, tỉ lệ không còn là tín hiệu.
DAI_TOI_THIEU_DE_SO_GAN = 8


def _chuan_so_gan(chu: str) -> str:
    """Bỏ dấu, bỏ mọi ký tự không phải chữ/số — chỉ để SO SÁNH.

    Không dùng cho nội dung gửi đi: đây chỉ là khoá nhận dạng "vẫn là caption
    đó". Bỏ khoảng trắng và dấu câu vì OCR hay chèn/nuốt chúng (`taidon` vs
    `x tai don`), mà đó không phải chữ khác.
    """
    import re
    import unicodedata

    tach = unicodedata.normalize("NFD", chu.lower())
    khong_dau = "".join(c for c in tach if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", khong_dau.replace("đ", "d"))


def _gan_giong(a: str, b: str) -> bool:
    """Hai khoá có phải cùng một caption không."""
    import difflib

    ka, kb = _chuan_so_gan(a), _chuan_so_gan(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if min(len(ka), len(kb)) < DAI_TOI_THIEU_DE_SO_GAN:
        return False
    return difflib.SequenceMatcher(None, ka, kb).ratio() >= NGUONG_GIONG_DE_GOP


def dai_dien_cua_doan(nhom: list[int], quan_sat: list) -> int:
    """Khung nào trong đoạn được gửi lên máy chủ.

    Lấy khung ĐỌC RÕ NHẤT, không phải khung đầu. Ca thật trong dữ liệu chủ dự
    án: `surersale` (0,944) rồi `supersale` (0,989) — gửi khung đầu là trả
    tiền để máy chủ đọc lại một khung vốn đã đọc sai. Chọn khung rõ nhất
    không tốn thêm đồng nào.
    """
    if not nhom:
        raise ValueError("đoạn rỗng")

    def _lay(q, ten, mac_dinh):
        # Nhận CẢ object lẫn dict, như `gop_quan_sat_lien_tiep` — bên gọi
        # trong dự án này dùng cả hai dạng.
        if isinstance(q, dict):
            return q.get(ten, mac_dinh)
        return getattr(q, ten, mac_dinh)

    diem: dict[int, float] = {}
    for q in quan_sat:
        khung = _lay(q, "frame_index", None)
        if khung in nhom:
            diem[khung] = min(diem.get(khung, 1.0),
                              float(_lay(q, "confidence", 0.0) or 0.0))
    if not diem:
        return nhom[0]
    # Hoà điểm thì lấy khung SỚM nhất — ổn định, không phụ thuộc thứ tự vào.
    return max(sorted(nhom), key=lambda i: diem.get(i, 0.0))


def _khoa_doan(quan_sat_cua_khung: list) -> str:
    """Dấu hiệu nhận biết "khung này đang hiện đúng chữ đó".

    Ghép nội dung các vùng chữ của MỘT khung theo thứ tự đọc (trên xuống, rồi
    trái sang phải). Dùng bản RapidOCR đọc được — mất dấu cũng không sao, vì
    ở đây chỉ cần so khung này với khung liền trước, không cần đọc hiểu.
    """
    sap = sorted(quan_sat_cua_khung, key=lambda q: (round(q.y, 2), round(q.x, 2)))
    return "".join(q.text.strip().lower() for q in sap if q.text.strip())


def chia_doan(quan_sat: list) -> list[list[int]]:
    """Chia các khung thành từng đoạn LIÊN TIẾP có cùng chữ.

    Trả về danh sách đoạn, mỗi đoạn là danh sách ``frame_index`` theo thứ tự
    tăng dần. Khung không có chữ nào không thuộc đoạn nào (không cần đọc lại).

    Chỉ gộp khung LIỀN KỀ nhau: cùng một câu caption xuất hiện, biến mất, rồi
    xuất hiện lại là hai lần hiện KHÁC nhau trên dòng thời gian — gộp chúng
    làm một là bịa ra một khoảng thời gian liên tục không có thật (cùng lý lẽ
    với `flow_blueprint.gop_quan_sat_lien_tiep`).
    """
    theo_khung: dict[int, list] = {}
    for q in quan_sat:
        theo_khung.setdefault(q.frame_index, []).append(q)

    doan: list[list[int]] = []
    khoa_truoc = None
    for chi_so in sorted(theo_khung):
        khoa = _khoa_doan(theo_khung[chi_so])
        if not khoa:
            khoa_truoc = None
            continue
        lien_tuc = (doan and khoa_truoc is not None
                    and chi_so == doan[-1][-1] + 1
                    and _gan_giong(khoa, khoa_truoc))
        if lien_tuc:
            doan[-1].append(chi_so)
        else:
            doan.append([chi_so])
        khoa_truoc = khoa
    return doan


#: Tên tệp chẩn đoán của E6 giai đoạn 0, nằm trong `<work_dir>/data/`.
TEP_CHAN_DOAN = "ocr_chan_doan.json"


def ghi_chan_doan_ocr(work_dir: str, quan_sat: list, *, transcript: list,
                      giay_ocr: float, dai_giay: float, so_moc: int,
                      thoi_gian_ocr: dict | None = None) -> None:
    """Ghi bằng chứng OCR ra đĩa để ĐO ĐƯỢC — E6 giai đoạn 0.

    Bước đọc chữ tốn 3 phút 51 giây và 88 Vox cho một video 34 giây (đo từ
    nhật ký chủ dự án 12/09). Có bốn đòn bẩy để cắt, nhưng không đòn bẩy nào
    CHỌN được nếu không có dữ liệu thật — mà dữ liệu đó tới giờ chỉ tồn tại
    trong bộ nhớ rồi biến mất cùng lượt chạy.

    Hàm này KHÔNG đổi hành vi gì, chỉ ghi thêm một tệp. Chỗ gọi nằm ở
    `flow_blueprint.trich_bang_chung`, ngay sau `read_text_regions` — tầng
    duy nhất có ĐỦ cả bằng chứng OCR lẫn transcript, mà câu hỏi C.1 ("bao
    nhiêu đoạn OCR trùng lời đọc") cần cả hai.

    Chi phí với người dùng là **0 Vox**: `read_text_regions` trả về bình
    thường kể cả khi họ bấm "Bỏ qua" ở cổng xin phép 50 Vox, nên dữ liệu đo
    vẫn có đủ mà không tiêu đồng nào.

    Ghi hỏng thì **chỉ cảnh báo**: chẩn đoán là thứ phụ, để nó giết lượt chạy
    của người dùng là thêm một tính năng đo đạc rồi chính nó gây sự cố.

    Xem `docs/MINI-SPEC_E6_Bot_Khung_OCR.md` cho bốn câu hỏi tệp này phải
    trả lời được.
    """
    import json
    import os

    try:
        doan = chia_doan(quan_sat)
        theo_khung: dict[int, list] = {}
        for q in quan_sat:
            theo_khung.setdefault(q.frame_index, []).append(q)

        muc = []
        for nhom in doan:
            cua_doan = [q for k in nhom for q in theo_khung.get(k, [])]
            moc = [q.timestamp_s for q in cua_doan
                   if getattr(q, "timestamp_s", None) is not None]
            muc.append({
                "khung": list(nhom),
                "bat_dau_s": round(min(moc), 3) if moc else None,
                "ket_thuc_s": round(max(moc), 3) if moc else None,
                # Chữ do RapidOCR đọc tại máy — mất dấu, đúng thứ cần để so
                # với transcript ở câu hỏi C.1.
                "chu_cuc_bo": _khoa_doan(theo_khung.get(nhom[0], [])),
                "so_vung": len(theo_khung.get(nhom[0], [])),
                "tin_cay_nho_nhat": round(
                    min((q.confidence for q in cua_doan), default=0.0), 3),
            })

        du_lieu = {
            "ghi_chu": ("E6 giai đoạn 0 — chỉ để đo, không ảnh hưởng kết quả. "
                        "Xem docs/MINI-SPEC_E6_Bot_Khung_OCR.md"),
            "video": {"dai_giay": dai_giay, "so_moc_lay_mau": so_moc},
            "thoi_gian": {
                "ocr_cuc_bo_s": round(giay_ocr, 2),
                # Tách khởi động engine khỏi phần quét từng khung — hai phần
                # phản ứng NGƯỢC nhau khi giảm số khung. Không có thì để
                # trống, KHÔNG đoán.
                **(thoi_gian_ocr or {}),
            },
            "doan": muc,
            # Cả hai phía mới trả lời được "bao nhiêu đoạn OCR trùng lời đọc".
            "transcript": [
                {"bat_dau_s": t.get("start_s"), "ket_thuc_s": t.get("end_s"),
                 "chu": t.get("text", "")}
                for t in (transcript or [])
            ],
        }
        thu_muc = os.path.join(work_dir, "data")
        os.makedirs(thu_muc, exist_ok=True)
        # Dựng chuỗi XONG rồi mới mở tệp: `open(p, "w")` cắt trắng tệp cũ
        # ngay cả khi phần dựng dữ liệu ném lỗi sau đó.
        tho = json.dumps(du_lieu, ensure_ascii=False, indent=2)
        with open(os.path.join(thu_muc, TEP_CHAN_DOAN), "w",
                  encoding="utf-8") as f:
            f.write(tho)
        logger.info("Đã ghi chẩn đoán OCR: %d đoạn / %d khung -> data/%s",
                    len(muc), len(theo_khung), TEP_CHAN_DOAN)
    except Exception as e:  # noqa: BLE001 — chẩn đoán không được giết lượt chạy
        logger.warning("Không ghi được chẩn đoán OCR (%s) — bỏ qua, lượt "
                       "chạy tiếp tục bình thường", e)


def _anh_gui_di(duong_dan: str) -> dict | None:
    """Thu nhỏ + mã hoá base64 một khung hình. Trả None nếu ảnh hỏng — thiếu
    một khung không được giết cả lượt đọc.

    Dùng **ffmpeg** qua `thu_nho_de_gui`, KHÔNG dùng PIL. Bản đầu của hàm này
    gọi `PIL.Image` — mà `autodub.spec` cố ý loại PIL khỏi bản đóng gói, luật
    đã ghi sẵn ở `product_scene.chuan_bi_anh()`. Hậu quả khi chạy từ tệp
    `.exe`: mọi khung đều trả None, không khung nào được gửi đi, H2b lặng lẽ
    rơi về bản đọc MẤT DẤU — tức là cổng 2 của pilot không bao giờ đóng được,
    và triệu chứng trông y hệt "mô hình đọc sai".
    """
    import os

    from autodub.product_scene import thu_nho_de_gui

    thu_muc = os.path.dirname(duong_dan) or "."
    ten_tam = f"_gui_{os.path.basename(duong_dan)}.jpg"
    try:
        return thu_nho_de_gui(duong_dan, thu_muc, ten_tam,
                              canh_dai=CANH_DAI_TOI_DA)
    except (OSError, ValueError) as e:
        logger.warning("Không chuẩn bị được khung hình %s (%s)", duong_dan, e)
        return None


def doc_lai_bang_may_chu(quan_sat: list, image_paths: list[str], *,
                         client=None, cancel_event=None, xin_phep=None) -> list:
    """Đọc lại nội dung chữ bằng mô hình nhìn ảnh, giữ nguyên dòng thời gian.

    ``quan_sat`` là kết quả RapidOCR tại máy (đã mất dấu). Hàm này giữ lại
    khung/mốc thời gian của chúng, chỉ THAY nội dung chữ bằng bản đọc đúng.

    ``xin_phep(so_vox, so_khung) -> bool`` được hỏi MỘT LẦN, trước lô đầu
    tiên, và chỉ khi số Vox dự tính vượt `NGUONG_XIN_PHEP_VOX`. Trả `False`
    thì giữ bản đọc cục bộ, không tiêu đồng nào. Không truyền thì chạy như cũ
    — mọi đường gọi nội bộ và 2.700 test sẵn có không đổi hành vi.

    Cổng nằm ở ĐÂY chứ không ở giao diện vì đường CLI và script cũng tiêu
    đúng số tiền đó.

    Hỏng ở bất kỳ đâu (chưa cấu hình máy chủ, mạng lỗi, hết Vox) thì **trả về
    nguyên bản đọc cục bộ**, không ném. Lý do: chữ mất dấu vẫn dùng được cho
    việc phân tích cấu trúc, còn ném lỗi ở đây là giết cả lượt phân tích chỉ
    vì phần làm-cho-đẹp-hơn không chạy được. Chỗ hỏng vẫn phải LỘ RA trong
    Nhật ký, không nuốt im lặng.
    """
    doan = chia_doan(quan_sat)
    if not doan:
        return quan_sat

    from autodub import saas_client
    if client is None:
        if not saas_client.is_configured():
            logger.info("Chưa cấu hình máy chủ VoxDub — giữ bản đọc tại máy "
                        "(chữ tiếng Việt sẽ không có dấu)")
            return quan_sat
        client = saas_client.SaasClient()

    dai_dien = [dai_dien_cua_doan(d, quan_sat) for d in doan]

    # Nói số Vox SẮP tiêu, TRƯỚC lượt gọi đầu tiên. Ghi sau thì dòng này chỉ
    # là biên lai. Đây là chỗ duy nhất biết được con số thật: nó phụ thuộc
    # lượng chữ trên hình, không phải độ dài video — lượt chạy thật 11/09
    # trên một video 34 giây ra 65 khung = 11 lô = 88 Vox, trong khi màn hình
    # lúc đó hứa "khoảng 32 Vox".
    so_lo = (len(dai_dien) + SO_KHUNG_MOI_LUOT - 1) // SO_KHUNG_MOI_LUOT
    du_tinh = so_lo * VOX_MOI_LO
    logger.info(
        "Đọc chữ qua máy chủ: %d khung cần đọc -> %d lô -> dự tính %d Vox "
        "(trừ dần theo lô, chỉ trừ lô nào chạy xong)",
        len(dai_dien), so_lo, du_tinh)

    if xin_phep is not None and du_tinh > NGUONG_XIN_PHEP_VOX:
        try:
            dong_y = bool(xin_phep(du_tinh, len(dai_dien)))
        except Exception as e:  # noqa: BLE001 — hộp thoại hỏng KHÔNG được
            # biến thành 88 Vox tiêu âm thầm. Nghiêng về phía không tiêu tiền.
            logger.warning("Không hỏi được người dùng về %d Vox (%s) — giữ "
                           "bản đọc tại máy cho chắc", du_tinh, e)
            dong_y = False
        if not dong_y:
            logger.info("Người dùng không đồng ý tiêu %d Vox — giữ bản đọc "
                        "tại máy (chữ tiếng Việt sẽ không có dấu)", du_tinh)
            return quan_sat

    doc_duoc: dict[int, list[str]] = {}

    for dau in range(0, len(dai_dien), SO_KHUNG_MOI_LUOT):
        if cancel_event is not None and cancel_event.is_set():
            break
        lo = dai_dien[dau:dau + SO_KHUNG_MOI_LUOT]
        anh = []
        khung_cua_anh = []
        for chi_so in lo:
            if chi_so >= len(image_paths):
                continue
            goi = _anh_gui_di(image_paths[chi_so])
            if goi is not None:
                anh.append(goi)
                khung_cua_anh.append(chi_so)
        if not anh:
            continue
        try:
            ket = client.assist(
                "doc_chu_khung_hinh", {"soAnh": len(anh)},
                job_id=saas_client.new_job_id(), images=anh)
        except Exception as e:  # noqa: BLE001 — mọi lỗi đều rơi về bản cục bộ
            logger.warning("Đọc chữ qua máy chủ hỏng (%s) — giữ bản đọc tại "
                           "máy cho lô này", e)
            continue
        for muc in ket or []:
            so = muc.get("anh") if isinstance(muc, dict) else None
            if not isinstance(so, int) or not 1 <= so <= len(khung_cua_anh):
                continue
            dong = [str(d).strip() for d in (muc.get("dong") or []) if str(d).strip()]
            doc_duoc[khung_cua_anh[so - 1]] = dong

    # Ghi lại đúng con số đã tiết kiệm được. Không có dòng này thì không ai
    # kiểm chứng được lời hứa "chỉ gửi khung đại diện" — mà đó là tiền thật:
    # mỗi khung gửi đi tốn ~1.150 token.
    logger.info(
        "Đọc chữ qua máy chủ: %d khung lấy mẫu -> %d đoạn chữ khác nhau -> "
        "gửi %d khung (%d khung đọc được kết quả)",
        len(image_paths), len(doan), len(dai_dien), len(doc_duoc))

    if not doc_duoc:
        return quan_sat

    return _ap_ket_qua(quan_sat, doan, doc_duoc)


def _ap_ket_qua(quan_sat: list, doan: list[list[int]],
                doc_duoc: dict[int, list[str]]) -> list:
    """Áp bản đọc đúng của khung đại diện cho MỌI khung trong cùng đoạn.

    Đoạn nào máy chủ không đọc được thì giữ nguyên quan sát cục bộ của đoạn
    đó — trộn được phần nào hay phần đó, không phải được-tất-cả-hoặc-không.
    """
    theo_khung: dict[int, list] = {}
    for q in quan_sat:
        theo_khung.setdefault(q.frame_index, []).append(q)

    # Khoá sắp xếp phụ = thứ tự ĐƯA VÀO, không phải nội dung chữ: phụ đề
    # song ngữ ("Excuse me" trên, "Xin lỗi" dưới) mà xếp theo chữ cái là đảo
    # mất thứ tự đọc trên→dưới của khung đó.
    ra: list[tuple[int, int, object]] = []
    da_xu_ly: set[int] = set()
    for cac_khung in doan:
        dai_dien = cac_khung[0]
        if dai_dien not in doc_duoc:
            continue
        dong = doc_duoc[dai_dien]
        for chi_so in cac_khung:
            da_xu_ly.add(chi_so)
            mau = theo_khung.get(chi_so) or []
            if not mau:
                continue
            # Giữ mốc thời gian của khung, thay nội dung. Không có dòng nào
            # (máy chủ đọc ra "khung này không chữ") thì khung đó biến mất
            # khỏi kết quả — đúng nghĩa "không có chữ", không phải giữ lại
            # bản đọc sai của OCR cục bộ.
            for thu_tu, van_ban in enumerate(dong):
                goc = mau[min(thu_tu, len(mau) - 1)]
                ra.append((chi_so, thu_tu, replace(
                    goc, text=van_ban, confidence=None, source="may_chu",
                    status="ok")))

    for chi_so, mau in theo_khung.items():
        if chi_so not in da_xu_ly:
            ra.extend((chi_so, thu_tu, q) for thu_tu, q in enumerate(mau))

    ra.sort(key=lambda muc: (muc[0], muc[1]))
    return [q for _khung, _thu_tu, q in ra]
