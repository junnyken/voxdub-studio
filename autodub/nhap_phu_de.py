"""Nhập một video + tệp phụ đề TIẾNG VIỆT SẴN thành dự án chỉnh sửa được.

Vì sao có tệp này (yêu cầu người dùng thật, 26/8/2026): *"tôi muốn lấy giọng
đọc .srt cho ra tiếng Việt ghép vào trong chỉnh sửa được không"* và *"ở chỗ
chỉnh sửa tôi có thể lấy video từ file… hay chỉ chỉnh sửa được video làm trên
tool này"*.

Câu trả lời lúc đó là chưa — Trình chỉnh sửa chỉ mở được thư mục dự án do
chính app tạo, và không có đường nào từ `.srt` sang giọng đọc. Nhưng mọi mảnh
đều đã có sẵn: đọc phụ đề, sinh giọng từng câu, ghép tiếng theo mốc, xuất
video. Thiếu đúng **một mảnh nối**: biến (video, phụ đề) thành thư mục dự án
đúng khuôn.

`nhap_du_an()` là bản cho phụ đề **đã là tiếng Việt**. Không dịch, không gọi
máy chủ, nên không tốn Vox — giọng đọc offline VieNeu lo phần còn lại.

`nhap_du_an_dich()` (08/09/2026, nối "chặng sau" đã ghi ở đây từ đầu) là bản
cho phụ đề **ngôn ngữ nước ngoài** — tự dịch sang ngôn ngữ đích trước khi
dựng dự án, dùng lại đúng hai đường dịch đã có: offline NLLB qua
`translate_local.run_local_worker` (miễn phí, chạy trên máy) hoặc SaaS qua
`saas_client.translate_subtitle` (**TÍNH PHÍ** theo dòng, cùng đơn giá
`credit.cost.segment.autotranslate` với trang Dịch phụ đề rời — không dựng
thêm đường dịch thứ ba, không hứa miễn phí cho đường này).

Ba chỗ chắc chắn vướng, xử ngay tại đây chứ không để bộ đọc gánh (áp dụng
cho cả hai hàm, vì cùng đọc một tệp phụ đề thật):

1. **Phụ đề hay cắt câu làm đôi** cho vừa dòng. Đọc thẳng từng dòng thì giọng
   ngắt cụt giữa câu — nên gộp lại bằng `gop_cau` (mini-spec C27) trước.
2. **Mốc chồng nhau**, hay gặp ở phụ đề tải từ mạng.
3. **Dòng rỗng / mốc lùi** — bỏ, nhưng phải ĐẾM và nói ra, không im lặng.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from autodub.languages import TargetLang, get_target
from autodub.utils import ensure_dir, setup_logging
from autodub.workdir import data_path

logger = setup_logging("autodub.nhap_phu_de")

#: Đuôi tệp video nhận vào — cùng danh sách với chỗ khác trong app.
DUOI_VIDEO = (".mp4", ".mov", ".mkv", ".avi", ".webm")


@dataclass
class KetQuaNhap:
    """Kết quả một lượt nhập."""

    thu_muc: str
    so_cau: int
    #: Những chỗ đã tự nắn hoặc bỏ — người dùng có quyền biết.
    canh_bao: list[str] = field(default_factory=list)
    #: Vox đã trừ — chỉ khác 0 khi dịch qua SaaS (`nhap_du_an_dich`, mode
    #: "saas"). `nhap_du_an` (phụ đề đã tiếng Việt) không tốn Vox nên luôn 0.
    credit_charged: int = 0


class LoiNhap(Exception):
    """Không nhập được, kèm câu nói rõ vì sao."""


def _giay(ts: str) -> float:
    from autodub.text.subtitle_parse import timestamp_to_seconds

    return float(timestamp_to_seconds(ts))


def cue_thanh_cau(cues) -> tuple[list[dict], list[str]]:
    """Đổi các dòng phụ đề thành câu thoại, kèm danh sách chỗ đã nắn."""
    canh_bao: list[str] = []
    tho: list[dict] = []
    bo_rong = 0
    bo_moc_hong = 0

    for c in cues:
        chu = " ".join(str(c.text or "").split())
        if not chu:
            bo_rong += 1
            continue
        try:
            dau, cuoi = _giay(c.start), _giay(c.end)
        except (ValueError, TypeError):
            bo_moc_hong += 1
            continue
        if cuoi <= dau:
            bo_moc_hong += 1
            continue
        tho.append({"start": dau, "end": cuoi, "text": chu})

    if bo_rong:
        canh_bao.append(f"Bỏ {bo_rong} dòng phụ đề không có chữ.")
    if bo_moc_hong:
        canh_bao.append(f"Bỏ {bo_moc_hong} dòng có mốc thời gian không hợp lệ.")

    tho.sort(key=lambda s: s["start"])

    # Mốc chồng nhau: kéo mốc kết thúc của dòng trước về sát dòng sau. Giữ
    # nguyên thì hai câu đọc chồng lên nhau lúc ghép tiếng.
    chong = 0
    for i in range(len(tho) - 1):
        if tho[i]["end"] > tho[i + 1]["start"]:
            tho[i]["end"] = tho[i + 1]["start"]
            chong += 1
    if chong:
        canh_bao.append(
            f"Nắn lại {chong} chỗ mốc thời gian chồng nhau — giữ nguyên thì "
            "hai câu sẽ đọc đè lên nhau.")

    return tho, canh_bao


def _dung_cau_tho(cues, *, gop: bool = True) -> tuple[list[dict], list[str]]:
    """Danh sách câu thoại thô (`id`/`start`/`end`/`duration`/`text`), CHƯA
    gán bản dịch — dùng chung cho cả đường phụ đề-đã-là-đích
    (:func:`dung_cau_thoai`) lẫn đường phụ đề-nước-ngoài
    (:func:`nhap_du_an_dich`, gán bản dịch sau khi có `by_id`)."""
    tho, canh_bao = cue_thanh_cau(cues)
    if not tho:
        raise LoiNhap(
            "Tệp phụ đề không có dòng nào dùng được. Kiểm tra lại tệp — cần "
            "định dạng .srt hoặc .vtt có mốc thời gian.")

    if gop:
        from autodub.transcribe_tool import gop_cau

        truoc = len(tho)
        tho = gop_cau(tho)
        if len(tho) < truoc:
            canh_bao.append(
                f"Gộp {truoc} dòng phụ đề thành {len(tho)} câu đọc được — "
                "phụ đề hay cắt câu làm đôi cho vừa dòng, đọc thẳng từng "
                "dòng thì giọng ngắt cụt giữa câu.")

    ra: list[dict] = []
    for i, s in enumerate(tho, 1):
        dau, cuoi = float(s["start"]), float(s["end"])
        chu = str(s["text"]).strip()
        ra.append({
            "id": i,
            "start": dau,
            "end": cuoi,
            "duration": round(cuoi - dau, 3),
            "text": chu,
        })
    return ra, canh_bao


def dung_cau_thoai(cues, *, gop: bool = True) -> tuple[list[dict], list[str]]:
    """Danh sách câu thoại hoàn chỉnh cho `transcript_<đích>.json` — phụ đề
    ĐÃ là ngôn ngữ đích, không cần dịch."""
    ra, canh_bao = _dung_cau_tho(cues, gop=gop)
    for s in ra:
        # Phụ đề đã là tiếng Việt: nó vừa là bản gốc vừa là bản đích. Giữ cả
        # hai trường để Trình chỉnh sửa hiện được cột đối chiếu.
        s["text_vi"] = s["text"]
    return ra, canh_bao


def _kiem_tra_video(video_path: str) -> None:
    if not os.path.isfile(video_path):
        raise LoiNhap(f"Không thấy tệp video: {video_path}")
    if not video_path.lower().endswith(DUOI_VIDEO):
        raise LoiNhap(
            "Tệp video phải có đuôi " + ", ".join(DUOI_VIDEO) + ".")


def _doc_phu_de(phu_de_path: str):
    """Đọc + parse một tệp `.srt`/`.vtt` thành `Cue` thô.

    Trả `(cues, so_khoi_bo_qua)` — `parse_subtitle` tự bỏ những khối sai
    khuôn trong tệp, đếm lại ở đây để bên gọi báo ra, không im lặng.
    """
    if not os.path.isfile(phu_de_path):
        raise LoiNhap(f"Không thấy tệp phụ đề: {phu_de_path}")

    from autodub.text.subtitle_parse import SubtitleParseError, parse_subtitle

    try:
        with open(phu_de_path, encoding="utf-8-sig") as f:
            noi_dung = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise LoiNhap(f"Không đọc được tệp phụ đề: {e}") from e
    # `parse_subtitle` nhận ĐỊNH DẠNG ("srt"/"vtt"), không nhận đường dẫn —
    # suy ra từ đuôi tệp tại đây.
    dinh_dang = os.path.splitext(phu_de_path)[1].lower().lstrip(".")
    if dinh_dang not in ("srt", "vtt"):
        raise LoiNhap(
            f"Chỉ nhận tệp phụ đề .srt hoặc .vtt (tệp bạn chọn có đuôi "
            f"«.{dinh_dang}»).")
    try:
        return parse_subtitle(noi_dung, dinh_dang)
    except SubtitleParseError as e:
        raise LoiNhap(f"Tệp phụ đề không đọc được: {e}") from e


def _dung_thu_muc_du_an(video_path: str, thu_muc_goc: str, target: TargetLang,
                        cau: list[dict], canh_bao: list[str], *,
                        ten_ngon_ngu_nguon: str) -> KetQuaNhap:
    """Phần đuôi dùng chung cho cả hai đường nhập: ghi transcript + đo/trích
    những thứ Trình chỉnh sửa cần đọc ra (C39)."""
    ten = datetime.now().strftime("%Y%m%d%H%M%S") + target.folder_suffix
    thu_muc = ensure_dir(os.path.join(thu_muc_goc, ten))

    with open(data_path(thu_muc, target.transcript_name, create_dir=True),
              "w", encoding="utf-8") as f:
        json.dump(cau, f, ensure_ascii=False, indent=2)

    with open(data_path(thu_muc, "source_video.json"), "w",
              encoding="utf-8") as f:
        json.dump({"file_path": os.path.abspath(video_path)}, f,
                  ensure_ascii=False, indent=2)

    # Bản đầu chỉ ghi phụ đề + đường dẫn video, nên dự án mở ra hiện «Thời
    # lượng 00:00», «Không đọc được dạng sóng của tệp âm thanh này» và
    # «Ngôn ngữ gốc: không rõ» — lỗi thật, chủ dự án báo ngay lượt dùng đầu
    # tiên (26/8/2026). Ba mảnh dưới đây là thứ đọc ra được từ chính video
    # đã có đường dẫn, không cần hỏi thêm người dùng câu nào.
    from autodub.media.video import probe_duration_s

    do_dai = probe_duration_s(video_path) or 0.0
    if not do_dai:
        canh_bao.append(
            "Không đo được độ dài video — Trình chỉnh sửa sẽ hiện thời lượng "
            "00:00. Không ảnh hưởng việc sửa hay xuất video.")

    # `report.json` là nơi trang Dự án và Trình chỉnh sửa đọc thời lượng ra
    # (xem autodub_gui/projects.py::_duration_of). Dự án nhập vào chưa từng
    # chạy nên chưa có tệp này — dựng bản tối thiểu, chỉ những trường đọc
    # được thật, KHÔNG bịa số đã xử lý hay số Vox.
    with open(data_path(thu_muc, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"total_original_duration": round(do_dai, 3),
                   "total_segments": len(cau),
                   "source_language": ten_ngon_ngu_nguon,
                   "nhap_tu_phu_de": True}, f, ensure_ascii=False, indent=2)

    # Âm thanh gốc: Trình chỉnh sửa vẽ dạng sóng từ tệp này. Không có nó thì
    # dải sóng trống trơn kèm dòng "Không đọc được dạng sóng".
    try:
        from autodub.media.audio import extract_audio

        extract_audio(video_path, data_path(thu_muc, "original_audio.wav"))
    except Exception as e:  # noqa: BLE001 — thiếu dạng sóng KHÔNG chặn việc sửa
        logger.warning("Không trích được âm thanh gốc (%s) — dự án vẫn dùng "
                       "được, chỉ thiếu dạng sóng trên thanh thời gian.", e)
        canh_bao.append(
            "Không trích được âm thanh gốc nên thanh thời gian sẽ không có "
            "dạng sóng. Mọi thứ khác vẫn dùng bình thường.")

    logger.info("Đã nhập %d câu vào %s", len(cau), thu_muc)
    return KetQuaNhap(thu_muc=thu_muc, so_cau=len(cau), canh_bao=canh_bao)


def nhap_du_an(video_path: str, phu_de_path: str, thu_muc_goc: str, *,
               target_key: str = "vi", gop: bool = True) -> KetQuaNhap:
    """Dựng thư mục dự án từ một video và một tệp phụ đề tiếng Việt.

    KHÔNG chép video — chỉ ghi nhớ đường dẫn trong `source_video.json`, đúng
    cách pipeline vẫn làm với tệp nằm ngoài thư mục dự án. Chép một tệp 2 GB
    chỉ để mở ra sửa là việc vô ích.
    """
    _kiem_tra_video(video_path)
    cues, bo_qua = _doc_phu_de(phu_de_path)

    cau, canh_bao = dung_cau_thoai(cues, gop=gop)
    if bo_qua:
        # `parse_subtitle` tự bỏ những khối sai khuôn. Im lặng thì người dùng
        # tưởng phụ đề của mình vào đủ.
        canh_bao.insert(0, f"Bỏ qua {bo_qua} khối phụ đề sai khuôn trong tệp.")

    target = get_target(target_key)
    return _dung_thu_muc_du_an(video_path, thu_muc_goc, target, cau, canh_bao,
                               ten_ngon_ngu_nguon=target.key)


def nhap_du_an_dich(
    video_path: str, phu_de_path: str, thu_muc_goc: str, *,
    source_flores: str, target_key: str = "vi", dich_mode: str = "local",
    settings=None, reporter=None, job_id: str | None = None,
    gop: bool = True,
) -> KetQuaNhap:
    """Dựng thư mục dự án từ một video và một tệp phụ đề NGÔN NGỮ NƯỚC NGOÀI
    — tự dịch sang `target_key` trước khi dựng dự án (nối "chặng sau" đã ghi
    ở đầu tệp này từ 26/8/2026, làm ngày 08/09/2026 theo yêu cầu người dùng).

    KHÔNG dựng đường dịch thứ ba: dùng lại đúng hai đường đã có trong
    :mod:`autodub.text.subtitle_translate` — offline NLLB
    (:func:`autodub.text.translate_local.run_local_worker`, `dich_mode="local"`)
    hoặc SaaS (:meth:`autodub.saas_client.SaasClient.translate_subtitle`,
    `dich_mode="saas"`). `source_flores`/`target_flores` là mã FLORES-200,
    cùng quy ước với trang Dịch phụ đề rời (V14) — KHÔNG suy đoán BCP-47→FLORES
    cho ~200 ngôn ngữ (Constraint 1 của V14); `target_key` (khoá `TargetLang`
    hẹp, đã đăng ký giọng đọc) tự quy ra FLORES qua bảng đã có
    `translate_local.LANG_TO_FLORES`, không dựng bảng mới.
    """
    from autodub.text.flores200 import display_name, is_known_flores_code
    from autodub.text.translate_local import flores_code as flores_tu_bcp47

    if dich_mode not in ("local", "saas"):
        raise LoiNhap(f"Cách dịch không hợp lệ: {dich_mode!r}.")
    if not is_known_flores_code(source_flores):
        raise LoiNhap(f"Mã ngôn ngữ phụ đề không hợp lệ: {source_flores!r}.")

    _kiem_tra_video(video_path)
    cues, bo_qua = _doc_phu_de(phu_de_path)
    cau, canh_bao = _dung_cau_tho(cues, gop=gop)
    if bo_qua:
        canh_bao.insert(0, f"Bỏ qua {bo_qua} khối phụ đề sai khuôn trong tệp.")

    target = get_target(target_key)
    target_flores = flores_tu_bcp47(target.code)
    if not target_flores:
        raise LoiNhap(
            f"Ngôn ngữ đích «{target.name}» chưa có mã FLORES-200 để dịch — "
            "chưa hỗ trợ tự dịch sang ngôn ngữ này.")
    if source_flores == target_flores:
        raise LoiNhap(
            "Ngôn ngữ phụ đề và ngôn ngữ đích giống nhau — không có gì để "
            "dịch. Dùng «Mở video + phụ đề tiếng Việt...» (không dịch) nếu "
            "phụ đề đã đúng ngôn ngữ đích.")

    items = [(s["id"], s["text"]) for s in cau]
    if dich_mode == "saas":
        import uuid

        from autodub.saas_client import get_client
        from autodub.saas_retry import call_with_retry

        client = get_client()
        data = call_with_retry(
            lambda: client.translate_subtitle(
                [{"id": i, "text": t} for i, t in items],
                job_id=job_id or f"nhap-{uuid.uuid4().hex}",
                source_flores=source_flores, target_flores=target_flores,
                source_name=display_name(source_flores),
                target_name=display_name(target_flores)),
            label="Dịch phụ đề khi nhập dự án")
        by_id = {seg.get("id"): seg.get("text", "")
                 for seg in data.get("segments", [])}
        credit_charged = int(data.get("creditCharged") or 0)
    else:
        if settings is None:
            raise LoiNhap("Thiếu cấu hình ứng dụng để dịch ngoại tuyến.")

        from autodub.text.translate_local import run_local_worker

        by_id = run_local_worker(items, source_flores, target_flores, settings,
                                 reporter, progress_step="nhap_phu_de_dich")
        credit_charged = 0

    thieu = 0
    for s in cau:
        dich = str(by_id.get(s["id"], "")).strip()
        if dich:
            s[target.text_field] = dich
        else:
            s[target.text_field] = s["text"]
            thieu += 1
    if thieu:
        canh_bao.append(
            f"Máy dịch không trả về {thieu} câu — giữ nguyên câu gốc cho "
            "những câu đó, bạn nên sửa tay trong Trình chỉnh sửa.")

    ket = _dung_thu_muc_du_an(
        video_path, thu_muc_goc, target, cau, canh_bao,
        ten_ngon_ngu_nguon=display_name(source_flores))
    ket.credit_charged = credit_charged
    return ket
