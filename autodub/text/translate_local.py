"""Dịch local/offline (mini-spec V6, xem docs/PLAN.md) — path C bên cạnh
dịch tay (path A) và dịch qua máy chủ (path B, xem translate_saas.py).

Chỉ dùng khi KHÔNG có máy chủ nào cấu hình (``saas_client.is_configured()``
== False — pipeline.py giữ nguyên gate đó làm cổng duy nhất) VÀ người dùng
đã bật ``settings.translate_local_enabled`` VÀ đã tải model
(``scripts/setup_translate_local.py``). Chạy 100% trên máy, không gọi mạng.

Chất lượng THẤP HƠN dịch tay (ChatGPT/Gemini) hoặc dịch qua máy chủ (3-pass
analyze→translate→review) — đây là bản dịch 1-pass, không có ngữ cảnh video.
Không giả vờ ngang hàng — GUI phải hiện rõ cảnh báo (xem
autodub_gui, trang Dịch thuật).

Giấy phép: model NLLB-200-distilled-600M là CC-BY-NC-4.0 (Meta) — CHỈ dùng
cho tính năng miễn phí của ứng dụng, không bán riêng bản dịch từ engine này.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import deque

from autodub.languages import TargetLang
from autodub.progress import ProgressReporter
from autodub.subprocess_watchdog import SubprocessTimeoutError, WatchedLineReader
from autodub.text.translate_hint import ensure_terminal_punct
from autodub.utils import bundled_file, setup_logging

logger = setup_logging("autodub.translate_local")

# mini-spec V24 (docs/PLAN.md, Phase F) — bug thật đã audit: đọc
# ``proc.stdout`` bằng vòng lặp chặn (`for line in proc.stdout:`) không có
# timeout tổng — nếu worker treo (model kẹt, deadlock hiếm), pipeline gọi
# nó treo VÔ THỜI HẠN. Giá trị dưới đây CHỦ ĐÍCH bảo thủ (rộng rãi, không
# phải benchmark thật) — mục tiêu là biến "treo vô hạn" thành "treo có
# trần", không phải tối ưu tốc độ phát hiện. Cấu hình lại cần dữ liệu thật
# từ nhiều lượt chạy — xem "Remaining Limits" mục V24 trong TEST_LOG.md.
_READY_TIMEOUT_S = 300     # nạp model NLLB 600MB int8 từ đĩa
_TRANSLATE_LINE_TIMEOUT_S = 120   # dịch xong 1 segment (có thể nhiều câu)

# BCP-47 (dùng trong app) -> FLORES-200 (dùng bởi NLLB). Gồm các ngôn ngữ
# nguồn đã có trong autodub_gui/dub_constants.py (V4) + mọi TargetLang.code
# đã đăng ký trong autodub/languages.py (V8/V11, mở rộng V17 — mã FLORES lấy
# từ đúng bảng 204 mã đã fetch thật trong flores200.py, không suy đoán).
LANG_TO_FLORES = {
    "zh-CN": "zho_Hans",
    "zh-TW": "zho_Hant",
    "zh-HK": "yue_Hant",   # Hồng Kông nói/viết phổ biến — Quảng Đông
    "en-US": "eng_Latn",
    "ko-KR": "kor_Hang",
    "ja-JP": "jpn_Jpan",
    "th-TH": "tha_Thai",
    "id-ID": "ind_Latn",
    "vi-VN": "vie_Latn",
    # Mini-spec V17 — thêm đích mới có giọng CapCut thật nhưng chưa có mã
    # nguồn ASR tương ứng (không phải nguồn V4, chỉ dùng làm ĐÍCH ở đây).
    "es-ES": "spa_Latn",
    "pt-BR": "por_Latn",
    "fr-FR": "fra_Latn",
    "de-DE": "deu_Latn",
}


class LocalTranslateError(Exception):
    """Dịch local hỏng (worker crash, model thiếu, ngôn ngữ không hỗ trợ)."""


class ChuaCaiDichNgoaiTuyen(LocalTranslateError):
    """Chưa cài bộ dịch ngoại tuyến — KHÁC HẲN "đã cài mà chạy hỏng".

    C61, lỗi thật người dùng báo: chọn "Máy này (offline, miễn phí)" ở trang
    Dịch phụ đề rời trên máy chưa chạy bộ cài thì `Popen` ném FileNotFoundError
    (không có python của `.venv-mt`), lỗi đó rơi thẳng ra giao diện thành
    *"Dừng lại vì một lỗi ngoài dự tính"*. Người dùng không có cách nào đoán ra
    việc cần làm là chạy một bộ cài.

    Cùng lớp lỗi với C56 ở bộ quét chữ: thiếu engine bị báo thành một câu vô
    nghĩa. Chưa cài là chuyện BÌNH THƯỜNG và đoán được — phải nói thẳng.
    """


def flores_code(bcp47: str) -> str | None:
    """FLORES-200 code cho 1 mã BCP-47, hoặc None nếu chưa map (chưa hỗ trợ)."""
    return LANG_TO_FLORES.get(bcp47)


def is_available(settings, source_lang: str) -> bool:
    """Đủ điều kiện dùng path C cho lượt này chưa (đã cài + ngôn ngữ hỗ trợ)."""
    return (bool(settings.translate_local_configured())
            and flores_code(source_lang) is not None)


def run_local_worker(
    items: list[tuple[int, str]], src: str, tgt: str, settings,
    reporter: ProgressReporter | None = None, progress_step: str = "translate",
    cancel_event=None,
) -> dict[int, str]:
    """Chạy ``translate_local_worker.py`` MỘT LẦN, trả về ``{id: bản dịch}``.

    Lõi dùng chung — mini-spec V14 (docs/PLAN.md) tách ra từ
    :func:`translate_segments_local` để dùng lại cho
    :mod:`autodub.text.subtitle_translate` (dịch 1 file phụ đề rời, không
    gắn với video nào đang lồng tiếng) mà không phải nhét dữ liệu vào hình
    dạng ``TargetLang``/segment của pipeline dub. ``src``/``tgt`` PHẢI đã là
    mã FLORES-200 (gọi :func:`flores_code` trước).
    """
    if not items:
        raise LocalTranslateError("Không có câu nào để dịch")

    # C61 — hỏi TRƯỚC khi chạy. Không có chốt này thì `Popen` ném
    # FileNotFoundError và người dùng nhận một câu vô nghĩa.
    # Hỏi đúng thứ sẽ hỏng: trình thông dịch của venv có tồn tại không. Dùng
    # `translate_local_configured()` ở đây thì chặn nhầm cả những lượt gọi hợp
    # lệ trỏ vào venv khác (bộ test watchdog dựng worker giả), mà vẫn không
    # chính xác hơn — thứ ném FileNotFoundError chính là tệp python này.
    if not os.path.isfile(settings.translate_local_venv_python_path()):
        raise ChuaCaiDichNgoaiTuyen(
            "Chưa cài bộ dịch ngoại tuyến trên máy này. Chạy "
            "«Cai dat dich ngoai tuyen.bat» (hoặc scripts/setup_translate_local.py) "
            "rồi dịch lại — bộ này nặng ~600 MB, tải một lần dùng mãi. "
            "Cần dịch ngay thì chọn «Máy chủ VoxDub» (tốn Vox, chất lượng cao hơn).")

    worker_script = bundled_file("autodub", "text", "translate_local_worker.py")
    cmd = [
        settings.translate_local_venv_python_path(),
        worker_script,
        "--model-dir", settings.translate_local_model_dir_path(),
        "--src-lang", src,
        "--tgt-lang", tgt,
    ]
    logger.info(f"Đang dịch {len(items)} câu bằng model local (offline)...")
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
        )
    except OSError as e:
        # Chốt ở trên đã hỏi `translate_local_configured()`, nhưng bộ cài có
        # thể cài dở (có thư mục model, thiếu venv). Vẫn phải là câu nói được
        # việc cần làm, không phải mã lỗi hệ điều hành.
        raise ChuaCaiDichNgoaiTuyen(
            f"Không chạy được bộ dịch ngoại tuyến ({e}). Chạy lại "
            "«Cai dat dich ngoai tuyen.bat» để cài cho đủ, hoặc chọn "
            "«Máy chủ VoxDub» để dịch ngay.") from e

    stderr_tail: deque[str] = deque(maxlen=30)
    import threading

    def _drain() -> None:
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    stderr_tail.append(line)
        except (ValueError, OSError):
            pass

    threading.Thread(target=_drain, daemon=True).start()
    reader = WatchedLineReader(proc)
    # Dịch cả video bằng model local mất nhiều phút; nút Dừng phải cắt ngang
    # được chứ không chỉ có tác dụng sau khi dịch xong (V79). Luồng canh tự
    # tắt khi worker thoát; việc đổi lỗi thành PipelineCancelled do
    # `translate_segments_local` lo.
    from autodub.cancel_guard import bat_dau_canh
    bat_dau_canh(proc, cancel_event)

    try:
        ready_line = reader.readline(_READY_TIMEOUT_S).strip()
    except SubprocessTimeoutError as e:
        proc.kill()
        # `from e`: giữ lại SubprocessTimeoutError làm __cause__ — mini-spec
        # V24 (Phase F) phân loại lỗi tạm thời/vĩnh viễn theo EXCEPTION TYPE
        # (autodub/batch_retry.py::is_transient_error), cần thấy được lỗi
        # GỐC xuyên qua lớp bọc LocalTranslateError này để nhận đúng "tạm
        # thời" thay vì mặc định "vĩnh viễn" (mặc định an toàn khi không rõ).
        raise LocalTranslateError(
            f"Worker dịch local không phản hồi trong {_READY_TIMEOUT_S}s "
            "khi nạp model — coi như treo.\n" + "\n".join(stderr_tail)) from e
    try:
        ready = json.loads(ready_line)
    except (json.JSONDecodeError, ValueError):
        proc.kill()
        raise LocalTranslateError(
            f"Worker dịch local không phản hồi: {ready_line!r}\n"
            + "\n".join(stderr_tail))
    if not ready.get("ready"):
        proc.kill()
        raise LocalTranslateError(
            f"Worker dịch local báo lỗi: {ready}\n" + "\n".join(stderr_tail))

    payload = {"segments": [{"id": item_id, "text": text}
                            for item_id, text in items]}
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    proc.stdin.close()

    by_id: dict = {}
    done = False
    try:
        while True:
            line = reader.readline(_TRANSLATE_LINE_TIMEOUT_S)
            if not line:
                break
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("error"):
                proc.wait(timeout=5)
                raise LocalTranslateError(f"Worker dịch local: {msg['error']}")
            if msg.get("seg"):
                by_id[msg.get("id")] = str(msg.get("text", ""))
                if reporter is not None:
                    reporter.emit(progress_step, "progress",
                                  current=len(by_id), total=len(items))
            elif msg.get("done"):
                done = True
                break
    except SubprocessTimeoutError as e:
        proc.kill()
        raise LocalTranslateError(
            f"Worker dịch local không phản hồi trong "
            f"{_TRANSLATE_LINE_TIMEOUT_S}s giữa lúc dịch — coi như treo "
            f"(đã dịch được {len(by_id)}/{len(items)} câu trước đó).\n"
            + "\n".join(stderr_tail)) from e

    proc.wait(timeout=30)
    if not done:
        raise LocalTranslateError(
            "Worker dịch local kết thúc bất thường\n" + "\n".join(stderr_tail))

    logger.info(f"Dịch local xong: {len(by_id)} câu")
    return by_id


def translate_segments_local(
    segments: list[dict], target: TargetLang, source_lang: str, settings,
    reporter: ProgressReporter | None = None, cancel_event=None,
) -> list[dict]:
    """Dịch toàn bộ câu bằng model local (NLLB, subprocess trong .venv-mt).

    Trả về bản sao ``segments`` kèm ``target.text_field``, cùng dạng dữ liệu
    với translate_saas.translate_segments() để pipeline.py không cần biết
    bản dịch đến từ đâu (xem điểm gọi trong DubPipeline._auto_translate()).
    """
    if not segments:
        raise LocalTranslateError("Không có câu nào để dịch")

    src = flores_code(source_lang)
    tgt = flores_code(target.code) or flores_code("vi-VN")
    if not src:
        raise LocalTranslateError(
            f"Dịch local chưa hỗ trợ ngôn ngữ nguồn '{source_lang}'")

    items = [(s.get("id"), s.get("text", "")) for s in segments]
    from autodub.cancel_guard import kiem_dung
    try:
        by_id = run_local_worker(items, src, tgt, settings, reporter,
                                 cancel_event=cancel_event)
    except Exception:
        # Giết tiến trình con làm bước này "hỏng" đủ kiểu; cú bấm Dừng phải
        # trông ra cú bấm Dừng, nếu không pipeline lại rơi sang "dịch tay".
        kiem_dung(cancel_event)
        raise

    # mini-spec V27 (docs/PLAN.md, Phase G) — bug thật: glossary
    # (`settings.translate_glossary`) trước đây CHỈ được enforce ở nhánh
    # SaaS (translate_hint.py::build_user_context_block, chèn vào prompt
    # LLM) — nhánh local NLLB không nhận prompt (seq2seq thuần) nên âm thầm
    # bỏ qua glossary hoàn toàn. Áp hậu xử lý tìm-thay-thế (cơ chế khả thi
    # DUY NHẤT cho NLLB — ctranslate2 không có API lexical-constraint, xem
    # translate_glossary_apply.py). Glossary rỗng -> parse_glossary() trả
    # [] -> apply_glossary() là no-op, hành vi y hệt trước V27.
    from autodub.text.translate_glossary_apply import apply_glossary, parse_glossary
    glossary_pairs = parse_glossary(getattr(settings, "translate_glossary", "") or "")

    merged = []
    for seg in segments:
        text = by_id.get(seg.get("id"), "")
        text = ensure_terminal_punct(text)
        if glossary_pairs:
            text = apply_glossary(seg.get("text", ""), text, glossary_pairs)
        merged.append({**seg, target.text_field: text})
    return merged
