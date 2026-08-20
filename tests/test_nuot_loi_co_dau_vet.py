"""V92 — mọi chỗ nuốt lỗi phải để lại dấu vết, hoặc được khai lý do.

Bài học đắt nhất tuần này: `except Exception` không kèm log làm trình cài đặt
tự động chết âm thầm **qua nhiều bản phát hành** (V83), và cùng cơ chế đó đã
giấu bốn lỗi khác (V75, V78, V86, V91).

Nhưng cấm tuyệt đối thì không thực tế: dọn dẹp, watchdog, probe chẩn đoán đều
có lý do chính đáng để im lặng. Nên luật ở đây là:

    Hoặc để lại dấu vết (log/raise/báo cho người dùng),
    hoặc có tên trong DANH SÁCH KHAI BÁO dưới đây kèm lý do.

Nhờ vậy "36 chỗ chấp nhận được" thôi là đánh giá trong đầu một người — nó
thành danh sách đọc được, và **thêm chỗ mới là test đỏ ngay**.
"""
from __future__ import annotations

import ast
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: (tệp, tên hàm) -> vì sao im lặng là ĐÚNG ở đây.
#: Thêm dòng vào đây là một quyết định, phải viết được lý do.
DUOC_IM_LANG = {
    # -- Dọn dẹp: đang trên đường thoát, kêu ca cũng không ai làm gì được --
    ("autodub/cancel_guard.py", "_canh_mot_tien_trinh"):
        "giết tiến trình đã chết rồi thì thôi",
    ("autodub/media/vocal_separator.py", "_shutdown"):
        "đóng worker lúc dọn dẹp",
    ("autodub/speech/align.py", "_asr_words_subprocess"):
        "đóng ống dữ liệu ở finally",
    ("autodub/speech/tts/voice_downloader.py", "_read_stderr"):
        "luồng đọc stderr, ống đóng đột ngột là bình thường",

    # -- Probe/chẩn đoán: kết quả CHÍNH LÀ True/False, hỏng cũng là dữ liệu --
    ("autodub_gui/app.py", "_probe_optional_imports"):
        "hỏng import chính là kết quả cần ghi vào báo cáo",
    ("autodub_gui/app.py", "_probe_env_file"):
        "ghi thẳng lý do vào checks[]",
    ("autodub/preflight.py", "run_preflight"):
        "tự dựng CheckResult mô tả lỗi",
    ("autodub_gui/setup_wizard.py", "_vieneu_ready"):
        "hỏng = coi như chưa cài, wizard hiện ra là đúng",
    ("autodub_gui/setup_wizard.py", "_whisper_ready"):
        "hỏng = coi như chưa cài",
    ("autodub/speech/tts/voice_downloader.py", "voices_installed"):
        "hỏng = coi như chưa cài",
    ("autodub/media/vocal_separator.py", "_probe_duration_s"):
        "không đọc được thời lượng thì dùng trần mặc định",
    ("autodub/saas_client.py", "_app_version"):
        "không đọc được phiên bản thì dùng mặc định",
    ("autodub/speech/tts/voice_downloader.py", "voices_release_url"):
        "cấu hình hỏng thì về kho mặc định",

    # -- Đường lui có tín hiệu khác cho người dùng --
    ("autodub/media/music_suggest.py", "goi_y_nhac_thong_minh"):
        "rơi về tầng luật, giao diện nói rõ nguồn gợi ý",
    ("autodub_gui/workers.py", "run"):
        "worker báo qua signal failed/finished, hoặc im lặng có chủ đích "
        "(ExplainErrorWorker: người đang bực vì lỗi không cần thêm thông báo)",
    ("autodub_gui/workers.py", "_voice_status"):
        "trả về 'không đọc được' hiện thẳng lên giao diện",
    ("autodub_gui/pages/editor_page.py", "_tighten_one"):
        "không đo được thời lượng thật thì ước theo tốc độ đọc",
    ("autodub_gui/pages/editor_page.py", "_load_render_opts"):
        "không đọc được danh sách người nói thì tắt nút đó",
    ("autodub_gui/pages/editor_page.py", "_on_export_options_changed"):
        "rơi về kiểu phụ đề mặc định",
    ("autodub_gui/pages/editor_export.py", "_open_style_dialog"):
        "hộp thoại vẫn mở được, chỉ thiếu câu xem trước",
    ("autodub_gui/pages/editor_panels.py", "_open_voice_popup"):
        "danh sách giọng rỗng thì popup vẫn mở",
    ("autodub_gui/icons.py", "app_logo"):
        "thiếu logo.ico thì vẽ tay",
    ("autodub_gui/app.py", "_maybe_first_run"):
        "nhánh dự phòng, nhánh chính đã có log",
    ("autodub_gui/app.py", "_prewarm_next"):
        "dựng sẵn trang cho mượt, hỏng thì dựng lúc mở",
    ("autodub/pipeline.py", "_progress_with_telemetry"):
        "callback giao diện hỏng không được chặn telemetry",
}


#: Mã CŨ chưa ai rà (đóng băng ngày 2026-08-20).
#:
#: Đây KHÔNG phải danh sách được duyệt — tôi chưa đọc từng chỗ này, nên khai
#: lý do cho chúng là nói dối. Nó chỉ nói: "đã có sẵn từ trước, và không được
#: phép nhiều thêm".
#:
#: Luật: danh sách này chỉ được NGẮN ĐI. Rà tới đâu thì hoặc thêm log, hoặc
#: chuyển sang DUOC_IM_LANG kèm lý do thật, rồi xoá khỏi đây.
CHUA_RA = {
    ("autodub/billing.py", "stop_for_export"),
    ("autodub/cloud_batch.py", "_try_submit"),
    ("autodub/editor.py", "suggest_voice"),
    ("autodub/keystore.py", "delete_secret"),
    ("autodub/media/demucs_worker.py", "serve"),
    ("autodub/progress.py", "emit"),
    ("autodub/speech/paraformer_transcriber.py", "transcribe_paraformer"),
    ("autodub/speech/transcriber.py", "_gpu_total_vram_gb"),
    ("autodub/speech/transcriber.py", "_transcribe_whisper_subprocess"),
    ("autodub/speech/tts/capcut_catalog.py", "device_profile"),
    ("autodub/speech/tts/vieneu_vi.py", "close"),
    ("autodub/speech/tts/vieneu_worker.py", "enroll_batch"),
    ("autodub/sysinfo.py", "_memory_status"),
    ("autodub/text/translate_saas.py", "_run_batch"),
    ("autodub/text/translate_saas.py", "analyze_transcript"),
    ("autodub_gui/crash.py", "_support_url"),
    ("autodub_gui/first_run.py", "_check_row"),
    ("autodub_gui/first_run.py", "maybe_show_first_run"),
    ("autodub_gui/fonts.py", "supports_vietnamese"),
    ("autodub_gui/pages/batch_page.py", "_build_options"),
    ("autodub_gui/pages/batch_page.py", "_cloud_dub_configured"),
    ("autodub_gui/pages/help_page.py", "_is_ready"),
    ("autodub_gui/pages/help_page.py", "_safe_settings"),
    ("autodub_gui/pages/home_page.py", "reload"),
    ("autodub_gui/pages/new_project_page.py", "_apply_defaults_from_settings"),
    ("autodub_gui/pages/new_project_page.py", "_base_style"),
    ("autodub_gui/pages/new_project_page.py", "_multi_speaker_on"),
    ("autodub_gui/pages/new_project_page.py", "_on_export_finished"),
    ("autodub_gui/pages/new_project_page.py", "_refresh_lipsync_info"),
    ("autodub_gui/pages/new_project_steps.py", "_default_voice"),
    ("autodub_gui/pages/new_project_steps.py", "load"),
    ("autodub_gui/pages/quality_page.py", "_scan_projects"),
    ("autodub_gui/pages/settings_panels.py", "_diagnostic_lines"),
    ("autodub_gui/pages/settings_panels.py", "_output_dir"),
    ("autodub_gui/pages/settings_panels.py", "_refresh_library_hint"),
    ("autodub_gui/pages/settings_panels.py", "_remove_cache_files"),
    ("autodub_gui/pages/settings_panels.py", "run"),
    ("autodub_gui/pages/voice_library.py", "_play"),
    ("autodub_gui/pages/voice_library.py", "_reload_voices"),
    ("autodub_gui/style_dialog.py", "_start_ocr_scan"),
    ("autodub_gui/style_dialog.py", "run"),
    ("autodub_gui/video/player.py", "_on_media_loaded_once"),
    ("autodub_gui/video/player.py", "open"),
    ("autodub_gui/voice_picker.py", "reload"),
    ("autodub_gui/voice_preview.py", "_library_wav"),
    ("autodub_gui/voice_preview.py", "cleanup"),
    ("autodub_gui/voice_preview.py", "run"),
    ("autodub_gui/voice_setup_dialog.py", "run"),
}

THU_MUC = ("autodub", "autodub_gui")
DAU_VET = ("log", "warn", "error", "info", "debug", "exception", "emit",
           "TOASTS", "print", "set_status", "set_music_status", "_die")


def _ham_chua(cay, node) -> str:
    ten = "?"
    for n in ast.walk(cay):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= node.lineno <= (n.end_lineno or n.lineno):
                ten = n.name
    return ten


def _co_dau_vet(node) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call) and any(
                k in ast.unparse(n.func) for k in DAU_VET):
            return True
    return False


def _quet() -> list[tuple[str, str, int]]:
    ra = []
    for muc in THU_MUC:
        for goc, _dirs, files in os.walk(os.path.join(REPO, muc)):
            if "__pycache__" in goc:
                continue
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                duong = os.path.join(goc, f)
                rel = os.path.relpath(duong, REPO)
                try:
                    cay = ast.parse(open(duong, encoding="utf-8").read())
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for n in ast.walk(cay):
                    if not isinstance(n, ast.ExceptHandler):
                        continue
                    ten = ast.unparse(n.type) if n.type else "bare"
                    if ten not in ("Exception", "BaseException", "bare"):
                        continue
                    if _co_dau_vet(n):
                        continue
                    ra.append((rel, _ham_chua(cay, n), n.lineno))
    return ra


def test_khong_co_cho_nuot_loi_nao_chua_khai_bao():
    """Chỗ nuốt lỗi MỚI phải có dấu vết hoặc lý do — không được thêm vào nợ."""
    biet = set(DUOC_IM_LANG) | CHUA_RA
    la = [(f, h, l) for f, h, l in _quet() if (f, h) not in biet]
    assert not la, (
        "Chỗ nuốt lỗi mà không để lại dấu vết nào và cũng chưa được khai:\n  "
        + "\n  ".join(f"{f}:{l} trong {h}()" for f, h, l in la)
        + "\n\nHoặc thêm log/raise, hoặc khai vào DUOC_IM_LANG kèm lý do."
    )


def test_danh_sach_khai_bao_khong_co_dong_thua():
    """Sửa mã cho tử tế rồi mà quên xoá khỏi danh sách thì danh sách phình
    lên và mất ý nghĩa — nó phải phản ánh đúng hiện trạng."""
    con = {(f, h) for f, h, _l in _quet()}
    thua = sorted(k for k in DUOC_IM_LANG if k not in con)
    assert not thua, f"Đã sửa xong nhưng vẫn còn trong danh sách: {thua}"


def test_no_cu_chi_duoc_ngan_di():
    """Danh sách "chưa rà" là NỢ, không phải chỗ chứa rác mới.

    Sửa xong một chỗ mà quên xoá khỏi đây thì lần sau không ai biết còn nợ
    thật là bao nhiêu — con số mất ý nghĩa, rồi cả danh sách bị bỏ qua.
    """
    con = {(f, h) for f, h, _l in _quet()}
    da_sua = sorted(k for k in CHUA_RA if k not in con)
    assert not da_sua, (
        "Đã sửa xong nhưng còn nằm trong CHUA_RA — xoá đi để con số nợ đúng: "
        f"{da_sua}")


def test_moi_dong_khai_bao_deu_co_ly_do_that():
    for khoa, ly_do in DUOC_IM_LANG.items():
        assert len(ly_do) > 20, f"{khoa}: lý do quá sơ sài"
