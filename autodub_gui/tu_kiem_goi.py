"""Lệnh chẩn đoán của BẢN ĐÓNG GÓI: chạy một lượt dub bằng chính `.exe`.

Mini-spec I0-FDE, **Route B**. Vì sao phải thêm lệnh thay vì dùng thứ có sẵn
(đã soi trước khi viết một dòng mã nào):

* `autodub_gui/__main__.py` gọi thẳng `app.main()`; `app.main()` không đọc
  `sys.argv` (chỉ chuyển cho `QApplication`) — bản `.exe` KHÔNG có dòng lệnh.
* `autodub/cli.py` không được nhập ở bất kỳ đâu trong `autodub_gui/`, nên
  PyInstaller không gói nó: trong `.exe` không có `voxdub dub`.
* Không có máy chủ nội bộ/IPC nào được bản đóng gói dựng lên để điều khiển.
* Cửa duy nhất hiện có là `AUTODUB_SMOKE=1`: dựng GUI rồi ghi
  `smoke_test_result.json`. Nó chứng minh app KHỞI ĐỘNG được — không chứng
  minh được nghe/đọc giọng/ghép video trong bản đóng gói.

Nên lệnh này là **lớp vỏ mỏng**, không phải đường ống thứ hai: nó dựng đúng
`DubRequest` rồi gọi `DubPipeline.run()` — CHÍNH lớp mà `autodub_gui/workers.py`
(`DubWorker.run`) gọi khi người dùng bấm nút, và cũng là lớp mà `autodub/cli.py`
gọi. Không có bước dub nào được viết lại ở đây.

Hai khoá an toàn, cả hai đều cần thiết:

1. Lệnh **tự khoá ngoại tuyến** (`AUTODUB_SMOKE=1` + `TRANSLATE_MODE=manual`).
   `saas_client.resolve_api_url()` trong bản đóng gói BỎ QUA biến môi trường
   và dùng địa chỉ nhúng trong exe, nên nếu không khoá thì mỗi lượt kiểm sẽ
   đăng ký một thiết bị mới trên máy chủ thật và tiêu một suất Vox dùng thử —
   chuyện này đã xảy ra thật ngày 22/8/2026. Khoá nằm TRONG lệnh chứ không
   phó thác cho người viết CI nhớ đặt biến.
2. Lệnh chỉ chạy khi có cờ `--tu-kiem-goi` ở dòng lệnh. Người dùng đúp chuột
   `VoxDub.exe` không bao giờ đi vào đây.

Dùng (chỉ CI gọi, qua `scripts/kiem_goi_phat_hanh.py`)::

    VoxDub.exe --tu-kiem-goi --chi-do-dac --bang-chung D:\\bc
    VoxDub.exe --tu-kiem-goi --video clip.mp4 --thu-muc-ra D:\\ra --bang-chung D:\\bc
    VoxDub.exe --tu-kiem-goi --video clip.mp4 --resume-dir D:\\ra\\2026…_vi --bang-chung D:\\bc

Mã thoát: 0 đạt · 2 tham số sai · 3 lượt chạy không tới đích · 4 lỗi ngoài dự
tính · 5 thiếu bộ máy bắt buộc.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

CO_TU_KIEM = "--tu-kiem-goi"

#: Mã thoát — đặt tên để nơi gọi (và test) không phải đoán con số.
MA_DAT = 0
MA_THAM_SO = 2
MA_KHONG_TOI_DICH = 3
MA_NGOAI_DU_TINH = 4
MA_THIEU_BO_MAY = 5

#: Bước của `autodub.progress.STEPS` → tên giai đoạn mà mini-spec I0-FDE đòi
#: trong `result.json`. Giai đoạn hỏng phải NÓI RA được, không được là một
#: câu "lỗi không rõ" — đó đúng là thứ làm mọi lần chẩn lỗi trước đây mất cả
#: buổi.
GIAI_DOAN_THEO_BUOC = {
    "acquire": "input",
    "extract": "input",
    "separate": "input",
    "asr": "asr",
    "diarize": "asr",
    "translate": "translation_fixture",
    "tts": "tts",
    "merge_audio": "merge",
    "merge_video": "merge",
    "content": "merge",
    "done": "probe",
}


class LoiThamSo(ValueError):
    """Tham số dòng lệnh không đủ/không hợp lệ."""


class _BoPhanTich(argparse.ArgumentParser):
    """argparse ném lỗi thay vì gọi ``sys.exit``.

    Bản `.exe` dựng với ``console=False`` nên ``sys.stderr`` là ``None``:
    đường báo lỗi mặc định của argparse không tới được ai. Tự cầm lỗi thì
    thông điệp còn đi vào ``result.json``.
    """

    def error(self, message):  # noqa: D102 — ghi đè API của argparse
        raise LoiThamSo(message)

    def exit(self, status=0, message=None):  # noqa: D102
        if status:
            raise LoiThamSo(message or f"tham số sai (mã {status})")


def co_yeu_cau_tu_kiem(argv=None) -> bool:
    """Dòng lệnh có yêu cầu chế độ tự kiểm bản đóng gói không."""
    return CO_TU_KIEM in list(argv if argv is not None else sys.argv[1:])


def phan_tich(argv) -> argparse.Namespace:
    ap = _BoPhanTich(prog=f"VoxDub.exe {CO_TU_KIEM}", add_help=False)
    ap.add_argument(CO_TU_KIEM, action="store_true", dest="tu_kiem")
    ap.add_argument("--bang-chung", dest="bang_chung", default="")
    ap.add_argument("--video", default="")
    ap.add_argument("--thu-muc-ra", dest="thu_muc_ra", default="")
    ap.add_argument("--resume-dir", dest="resume_dir", default="")
    ap.add_argument("--chi-do-dac", dest="chi_do_dac", action="store_true")
    ap.add_argument("--source-lang", dest="source_lang", default="auto")
    ap.add_argument("--voice", default="")
    ap.add_argument("--doi-bo-may", dest="doi_bo_may", default="",
                    help="danh sách bộ máy BẮT BUỘC phải sẵn sàng, "
                         "vd 'vieneu,whisper'")
    args = ap.parse_args(list(argv))

    if not args.bang_chung:
        raise LoiThamSo("thiếu --bang-chung: không có chỗ ghi bằng chứng thì "
                        "lượt kiểm này không chứng minh được gì")
    if args.chi_do_dac:
        return args
    if not args.video:
        raise LoiThamSo("thiếu --video (tệp mẫu để chạy thử)")
    if not os.path.isfile(args.video):
        raise LoiThamSo(f"không thấy tệp mẫu: {args.video}")
    if not args.thu_muc_ra and not args.resume_dir:
        raise LoiThamSo("cần --thu-muc-ra (lượt mới) hoặc --resume-dir "
                        "(chạy tiếp lượt dở)")
    if args.resume_dir and not os.path.isdir(args.resume_dir):
        raise LoiThamSo(f"không thấy thư mục chạy tiếp: {args.resume_dir}")
    return args


def khoa_ngoai_tuyen() -> dict:
    """Khoá lượt kiểm vào đường NGOẠI TUYẾN, trả về các biến đã đặt.

    Phải gọi TRƯỚC khi nhập `autodub.config`/`autodub.saas_client`.
    """
    dat = {
        # Cửa chặn DUY NHẤT đã có sẵn trong mã sản phẩm (saas_client.py:100).
        # Không tự chế cửa thứ hai.
        "AUTODUB_SMOKE": "1",
        "TRANSLATE_MODE": "manual",
        "TRANSLATE_LOCAL_ENABLED": "0",
        "TRANSLATE_ANALYSIS": "0",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    os.environ.update(dat)
    return dict(dat)


def _ghi_nhat_ky_tien_trinh_con(duong_jsonl: str) -> list:
    """Ghi lại MỌI tiến trình con app khởi chạy (đường dẫn + tham số).

    Đây là bằng chứng trung tâm của I0-F: engine nặng phải chạy qua tiến
    trình con của venv nằm TRONG hộp cát. Nếu một lượt chạy "xanh" nhờ mượn
    python/worker của cây mã nguồn thì dòng nhật ký này là nơi duy nhất nhìn
    ra được.

    Cách vá dùng chung lối đã có trong `autodub_gui/_frozen.py`
    (`_hide_subprocess_windows`) — vá một chỗ, không rải cờ ra từng lời gọi.
    """
    da_ghi: list = []
    goc = subprocess.Popen.__init__

    def _ghi(self, *args, **kwargs):
        try:
            lenh = kwargs.get("args", args[0] if args else None)
            if isinstance(lenh, (list, tuple)):
                chuong_trinh = str(lenh[0]) if lenh else ""
                tham_so = [str(x) for x in list(lenh)[1:]]
            else:
                chuong_trinh, tham_so = str(lenh), []
            from autodub.bang_chung import che_bi_mat
            muc = che_bi_mat({
                "luc": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "chuong_trinh": chuong_trinh,
                "tham_so": tham_so,
                "cwd": str(kwargs.get("cwd") or os.getcwd()),
            })
            da_ghi.append(muc)
            with open(duong_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps(muc, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001 — ghi bằng chứng KHÔNG được làm vỡ app
            pass
        return goc(self, *args, **kwargs)

    subprocess.Popen.__init__ = _ghi
    return da_ghi


def do_dac_bo_may(settings) -> dict:
    """Bộ máy nào đang SẴN SÀNG, và đường dẫn thật của chúng.

    Đây vừa là bằng chứng của I0-D ("hộp cát sạch, không mượn của ai") vừa là
    bằng chứng của I0-E ("dùng lại đúng bản cũ nằm cạnh") — vì các hàm dưới
    đây chính là chỗ `Settings` quyết định dùng lại bản cài cũ
    (`autodub/config.py::_ban_cu` → `autodub/venv_discovery.py`).
    """
    import shutil

    from autodub.utils import app_root, gpu_venv_dir
    from autodub.venv_discovery import tim_env_cu, tim_thu_muc_bin_cu

    def _muc(python: str, model: str, san_sang: bool) -> dict:
        return {"python": python, "thu_muc_model": model,
                "san_sang": bool(san_sang)}

    goc = app_root()
    return {
        "app_root": goc,
        "vieneu": _muc(settings.vieneu_venv_python_path(),
                       settings.vieneu_model_dir_path(),
                       settings.vieneu_configured()),
        "whisper": _muc(settings.whisper_venv_python_path(),
                        settings.whisper_model_dir_path(),
                        settings.whisper_venv_configured()),
        "paraformer": _muc(settings.asr_venv_python_path(),
                           settings.paraformer_model_dir_path(),
                           settings.paraformer_configured()),
        "ffmpeg": shutil.which("ffmpeg") or "",
        "ffprobe": shutil.which("ffprobe") or "",
        "venv_gpu": gpu_venv_dir(),
        # `.env`: chỉ ghi ĐƯỜNG DẪN và việc có/không, KHÔNG bao giờ nội dung.
        "env_cua_ban_nay": os.path.join(goc, ".env"),
        "env_cua_ban_nay_co": os.path.isfile(os.path.join(goc, ".env")),
        "env_ban_cu_tim_thay": tim_env_cu(),
        "bin_ban_cu_tim_thay": tim_thu_muc_bin_cu(),
    }


def _ghi_ket_qua(duong: str, du_lieu: dict) -> None:
    from autodub.bang_chung import che_bi_mat
    from autodub.utils import save_json_atomic

    save_json_atomic(che_bi_mat(du_lieu), duong)


def chay(argv=None) -> int:
    """Chạy chế độ tự kiểm; trả về mã thoát."""
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        args = phan_tich(argv)
    except LoiThamSo as e:
        # Chưa chắc có thư mục bằng chứng hợp lệ — cố ghi nếu người gọi đã
        # chỉ ra chỗ, còn không thì chỉ còn mã thoát để nói.
        for i, x in enumerate(argv):
            if x == "--bang-chung" and i + 1 < len(argv):
                try:
                    os.makedirs(argv[i + 1], exist_ok=True)
                    _ghi_ket_qua(os.path.join(argv[i + 1], "result.json"),
                                 {"ket_qua": "hong",
                                  "giai_doan_hong": "startup",
                                  "loi": f"tham số: {e}"})
                except OSError:
                    pass
        return MA_THAM_SO

    bang_chung = os.path.abspath(args.bang_chung)
    os.makedirs(bang_chung, exist_ok=True)
    ket_qua_json = os.path.join(bang_chung, "result.json")
    moi_truong = khoa_ngoai_tuyen()

    ket: dict = {
        "phien_ban_cong": "I0-FDE/1",
        "ket_qua": "hong",
        "giai_doan_hong": "startup",
        "trang_thai_pipeline": "",
        "bat_dau": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ung_dung": {
            "executable": os.path.abspath(sys.executable),
            "dong_bang": bool(getattr(sys, "frozen", False)),
            "meipass": getattr(sys, "_MEIPASS", ""),
            "argv": argv,
        },
        "moi_truong_khoa": moi_truong,
    }
    try:
        # Đúng thứ tự khởi động của bản đóng gói: `app.main()` gọi
        # `_frozen.init()` trước mọi thứ khác (PATH của ffmpeg/bin, neo thư
        # mục làm việc cạnh exe). Bỏ bước này là đang kiểm một app khác.
        from autodub_gui import _frozen

        _frozen.init()
        from autodub.utils import app_root, init_file_logging

        ket["ung_dung"]["app_root"] = app_root()
        ket["ung_dung"]["nhat_ky"] = init_file_logging()

        theo_doi = _ghi_nhat_ky_tien_trinh_con(
            os.path.join(bang_chung, "worker-launches.jsonl"))

        from autodub.config import Settings
        from autodub.saas_client import resolve_api_url

        settings = Settings.load()
        ket["ung_dung"]["dia_chi_may_chu"] = resolve_api_url()
        ket["ung_dung"]["ngoai_tuyen"] = not resolve_api_url()
        ket["bo_may"] = do_dac_bo_may(settings)

        thieu = [ten for ten in
                 [t.strip() for t in args.doi_bo_may.split(",") if t.strip()]
                 if not ket["bo_may"].get(ten, {}).get("san_sang")]
        if thieu:
            ket.update({"giai_doan_hong": "bo_may_thieu", "bo_may_thieu": thieu,
                        "loi": "Bộ máy bắt buộc chưa sẵn sàng trong thư mục "
                               f"ứng dụng này: {', '.join(thieu)}"})
            _ghi_ket_qua(ket_qua_json, ket)
            return MA_THIEU_BO_MAY

        if args.chi_do_dac:
            ket.update({"ket_qua": "dat", "giai_doan_hong": None,
                        "chi_do_dac": True,
                        "tien_trinh_con": len(theo_doi)})
            _ghi_ket_qua(ket_qua_json, ket)
            return MA_DAT

        # --- Lượt dub thật, qua ĐÚNG lớp mà giao diện dùng -----------------
        from autodub.pipeline import DubPipeline, DubRequest

        cac_buoc: list[dict] = []
        duong_tien_do = os.path.join(bang_chung, "pipeline-progress.jsonl")

        def _tien_do(su_kien) -> None:
            muc = {"buoc": su_kien.step, "trang_thai": su_kien.status,
                   "chi_tiet": su_kien.detail, "hien_tai": su_kien.current,
                   "tong": su_kien.total}
            cac_buoc.append(muc)
            try:
                with open(duong_tien_do, "a", encoding="utf-8") as f:
                    f.write(json.dumps(muc, ensure_ascii=False) + "\n")
            except OSError:
                pass

        yeu_cau = DubRequest(
            file_path=os.path.abspath(args.video),
            source_lang=args.source_lang,
            voice=args.voice or None,
            bg_mode="none",          # bỏ Demucs: nặng, không thuộc đường kiểm
            subtitle_mode="none",
            skip_video=bool(args.thu_muc_ra and not args.resume_dir),
            output_dir=os.path.abspath(args.thu_muc_ra) if args.thu_muc_ra else None,
            resume_dir=os.path.abspath(args.resume_dir) if args.resume_dir else None,
        )
        ket["yeu_cau"] = {
            "file_path": yeu_cau.file_path, "source_lang": yeu_cau.source_lang,
            "bg_mode": yeu_cau.bg_mode, "subtitle_mode": yeu_cau.subtitle_mode,
            "skip_video": yeu_cau.skip_video, "output_dir": yeu_cau.output_dir,
            "resume_dir": yeu_cau.resume_dir,
        }

        duong_ong = DubPipeline(settings, progress=_tien_do)
        bat_dau = time.time()
        ket_dub = duong_ong.run(yeu_cau)
        ket["giay_chay"] = round(time.time() - bat_dau, 1)
        ket["tien_trinh_con"] = len(theo_doi)
        ket["trang_thai_pipeline"] = ket_dub.status
        ket["thu_muc_lam_viec"] = ket_dub.work_dir
        ket["bao_cao"] = ket_dub.report
        ra = os.path.join(ket_dub.work_dir or "", "dubbed_video.mp4")
        ket["video_ra"] = ra if os.path.isfile(ra) else ""

        # Chặng 1 (lượt mới, dịch TAY) dừng đúng ở `translate_pending`; chặng
        # 2 (chạy tiếp) phải đi tới `completed`. Nhận bừa `translate_pending`
        # ở chặng 2 là tự cho mình điểm cho một lượt chưa hề xuất video —
        # đúng lớp "mã thoát 0 mà sản phẩm không có" mà C55 đã chữa một lần.
        mong_doi = ("completed",) if args.resume_dir \
            else ("translate_pending", "completed")
        ket["trang_thai_mong_doi"] = list(mong_doi)
        if ket_dub.status in mong_doi:
            ket.update({"ket_qua": "dat", "giai_doan_hong": None})
            _ghi_ket_qua(ket_qua_json, ket)
            return MA_DAT
        ket["giai_doan_hong"] = _giai_doan_cuoi(cac_buoc)
        ket["loi"] = (f"Đường ống dừng ở trạng thái {ket_dub.status!r}, "
                      f"mong đợi một trong {mong_doi}.")
        _ghi_ket_qua(ket_qua_json, ket)
        return MA_KHONG_TOI_DICH
    except Exception as e:  # noqa: BLE001 — mọi lỗi phải thành bằng chứng
        import traceback

        ket["loi"] = f"{type(e).__name__}: {e}"
        ket["vet_loi"] = traceback.format_exc()[-4000:]
        buoc = locals().get("cac_buoc") or []
        ket["giai_doan_hong"] = _giai_doan_cuoi(buoc) if buoc else \
            ket.get("giai_doan_hong") or "unexpected"
        try:
            _ghi_ket_qua(ket_qua_json, ket)
        except Exception:  # noqa: BLE001 — đây là lần ghi bằng chứng CUỐI
            # CÙNG (đĩa đầy, thư mục bị khoá…). Ném tiếp ở đây chỉ đổi một
            # lỗi nói được thành traceback không ai đọc; mã thoát khác 0 bên
            # dưới vẫn giữ nguyên kết luận "lượt này hỏng".
            pass
        return MA_NGOAI_DU_TINH


def _giai_doan_cuoi(cac_buoc: list) -> str:
    """Giai đoạn (theo từ vựng I0-FDE) mà lượt chạy dừng lại ở đó."""
    for muc in reversed(cac_buoc):
        if muc.get("trang_thai") == "error":
            return GIAI_DOAN_THEO_BUOC.get(muc.get("buoc", ""), "unexpected")
    for muc in reversed(cac_buoc):
        if muc.get("buoc"):
            return GIAI_DOAN_THEO_BUOC.get(muc["buoc"], "unexpected")
    return "startup"
