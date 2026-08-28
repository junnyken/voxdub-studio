"""Máy thiếu bộ nhớ thì lùi bậc model, đừng giết cả lượt chạy (mini-spec C46).

Lỗi thật, chủ dự án gặp ngay ở bản v3.14.0 (28/08/2026):

* Máy dùng card Intel. Nạp được `cublas64_*.dll` (nó nằm sẵn trong thư mục
  torch) nên app tưởng có CUDA, thử ba lượt float16/int8_float16/int8 rồi mới
  chịu rơi xuống CPU — nhật ký đầy chữ "CUDA out of memory" gây hiểu nhầm là
  card yếu.
* Rơi xuống CPU thì worker gọi `_resolve_model("auto", False)`, tức **nuốt
  lựa chọn của người dùng**: chọn `large-v3` mà câu lỗi lại nói `medium`.
* `medium` không nạp nổi vì thiếu RAM → cả lượt chạy chết với đúng một câu
  `mkl_malloc: failed to allocate memory`. Không ai đoán ra việc cần làm là
  hạ mức "Độ chính xác" ở bước Nhận dạng.
"""
from __future__ import annotations

import os
import re

import pytest

from autodub.speech import transcriber

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(GOC, "autodub", "speech", "asr_whisper_worker.py")


class _HetBoNho(Exception):
    pass


@pytest.fixture(autouse=True)
def _ram_co_dinh(monkeypatch):
    """Cố định RAM "còn trống" cho mọi test trong tệp.

    Không cố định thì bài kiểm bậc lùi phụ thuộc vào máy đang chạy test rảnh
    hay bận — đỏ lúc này xanh lúc khác, đúng kiểu test bị tắt sau vài lần.
    (Chính tệp này đã đỏ một lượt vì lý do đó.)"""
    monkeypatch.setattr(transcriber, "available_ram_gb", lambda: 64.0)


def _may_gia(nap_duoc: set[str]):
    """WhisperModel giả: chỉ nạp được những model trong `nap_duoc`."""
    da_thu: list[str] = []

    def _tao(ten, **_kw):
        da_thu.append(ten)
        if ten not in nap_duoc:
            raise _HetBoNho("mkl_malloc: failed to allocate memory")
        return f"model:{ten}"

    return _tao, da_thu


def test_lui_dan_tung_bac_chu_khong_nhay_xuong_day():
    tao, da_thu = _may_gia({"small"})
    model = transcriber._nap_cpu_co_bac_lui(tao, "large-v3")
    assert model == "model:small"
    assert da_thu == ["large-v3", "large-v2", "medium", "small"], (
        "phải lùi từng bậc một, không nhảy thẳng xuống đáy")


def test_model_nap_duoc_ngay_thi_khong_dung_toi_bac_lui():
    tao, da_thu = _may_gia({"medium"})
    assert transcriber._nap_cpu_co_bac_lui(tao, "medium") == "model:medium"
    assert da_thu == ["medium"]


def test_loi_KHONG_phai_thieu_bo_nho_thi_nem_nguyen_van():
    """Thiếu tệp model hay hỏng mạng mà cũng lùi bậc thì chỉ hỏng chậm hơn,
    và giấu mất nguyên nhân thật."""
    def _tao(ten, **_kw):
        raise RuntimeError("Repository not found: openai/whisper-large-v3")

    with pytest.raises(RuntimeError, match="Repository not found"):
        transcriber._nap_cpu_co_bac_lui(_tao, "large-v3")


def test_het_bac_thi_bao_viec_that_phai_lam():
    tao, _ = _may_gia(set())
    with pytest.raises(RuntimeError) as e:
        transcriber._nap_cpu_co_bac_lui(tao, "tiny")
    loi = str(e.value)
    assert "Đóng bớt ứng dụng" in loi, "câu lỗi phải nói việc thật phải làm"
    assert "không bị trừ Vox" in loi, (
        "người dùng thấy lượt chạy chết giữa chừng sẽ mặc định là mình vừa mất "
        "tiền — phải nói rõ")


def test_ten_model_la_van_co_loi_thoat():
    tao, da_thu = _may_gia({"small"})
    assert transcriber._nap_cpu_co_bac_lui(tao, "ban-fine-tune-rieng") == "model:small"


# ------------------- hai đường ASR phải cùng một bậc lùi -------------------

def test_worker_va_in_process_dung_CHUNG_mot_bang_bac():
    """Lớp lỗi #2 của dự án: sửa một trong hai đường. Worker chạy trong
    `.venv-whisper` nên không import được `autodub`, đành chép bảng — vậy thì
    phải có bộ canh cho chỗ chép đó."""
    src = open(WORKER, encoding="utf-8").read()
    khoi = re.search(r"_BAC_MODEL = \[(.*?)\]", src, re.S).group(1)
    bac_worker = re.findall(r'"([^"]+)"', khoi)
    assert bac_worker == transcriber.BAC_MODEL

    khoi2 = re.search(r"_DAU_HIEU_HET_BO_NHO = \((.*?)\)", src, re.S).group(1)
    dau_hieu = tuple(re.findall(r'"([^"]+)"', khoi2))
    assert dau_hieu == transcriber.DAU_HIEU_HET_BO_NHO


def test_worker_khong_con_nuot_lua_chon_cua_nguoi_dung():
    src = open(WORKER, encoding="utf-8").read()
    assert 'model_name = _resolve_model("auto", False)\n                model = WhisperModel' not in src
    # Chỉ được quy về "auto" khi người dùng THẬT SỰ chọn auto.
    assert 'if args.model.strip().lower() == "auto":' in src


def test_worker_hoi_that_xem_co_card_nvidia_khong():
    """Nạp được cuBLAS không có nghĩa là máy có card NVIDIA — DLL đó nằm sẵn
    trong thư mục torch."""
    src = open(WORKER, encoding="utf-8").read()
    assert "get_cuda_device_count" in src
    assert "Không thấy card NVIDIA" in src


# --------------- chọn ĐÚNG BẬC ngay từ đầu, đừng tải rồi mới biết ---------------

@pytest.mark.parametrize("chon,ram,mong_doi", [
    ("large-v3", 8.0,  "large-v3"),   # máy khoẻ: giữ nguyên lựa chọn
    ("large-v3", 2.5,  "medium"),     # đúng ca máy chủ dự án
    ("large-v3", 1.2,  "small"),
    ("medium",   0.5,  "tiny"),
    ("small",    8.0,  "small"),      # KHÔNG bao giờ nâng quá lựa chọn
    ("large-v3", 0.0,  "large-v3"),   # không đọc được RAM → đừng tự ý hạ
    ("large-v3", 0.1,  "tiny"),       # RAM tí xíu: xuống đáy chứ không chết
])
def test_chon_bac_theo_ram_con_trong(chon, ram, mong_doi):
    assert transcriber._model_vua_ram(chon, ram) == mong_doi


def test_khong_tai_ve_bac_nao_khong_dung_toi(monkeypatch):
    """Lùi bậc SAU khi nạp hỏng thì mỗi bậc phải tải về vài GB rồi mới biết là
    không nạp nổi — người dùng chờ hàng chục phút cho việc đằng nào cũng hỏng."""
    monkeypatch.setattr(transcriber, "available_ram_gb", lambda: 1.2)
    tao, da_thu = _may_gia({"small"})
    assert transcriber._nap_cpu_co_bac_lui(tao, "large-v3") == "model:small"
    assert da_thu == ["small"], f"đã tải thừa: {da_thu}"


def test_bang_RAM_cua_hai_duong_khop_nhau():
    src = open(WORKER, encoding="utf-8").read()
    khoi = re.search(r"_RAM_CAN_GB = \{(.*?)\}", src, re.S).group(1)
    bang = {k: float(v) for k, v in re.findall(r'"([^"]+)": ([\d.]+)', khoi)}
    assert bang == transcriber.RAM_CAN_GB


def test_ram_di_bang_BIEN_MOI_TRUONG_chu_khong_phai_tham_so_dong_lenh():
    """Lỗi thật (chủ dự án, 28/08): cha bản mới gửi `--ram-trong-gb` xuống một
    worker bản CŨ; argparse gặp tham số lạ liền sys.exit(2) — CHẾT CẢ LƯỢT
    CHẠY vì một tính năng chỉ để chọn model cho khéo.

    Biến môi trường thì worker đời cũ bỏ qua trong im lặng. Từ nay tham số MỚI
    giữa cha và worker đi bằng biến môi trường; dòng lệnh chỉ dành cho thứ đã
    có từ đầu."""
    src = open(os.path.join(GOC, "autodub", "speech", "transcriber.py"),
               encoding="utf-8").read()
    assert '"--ram-trong-gb"' not in src, (
        "cha vẫn gửi RAM qua dòng lệnh — worker đời cũ sẽ chết vì tham số lạ")
    assert 'moi_truong["VOXDUB_RAM_TRONG_GB"]' in src
    assert "env=moi_truong" in src, "đặt biến rồi mà không truyền cho tiến trình con"

    w = open(WORKER, encoding="utf-8").read()
    assert "VOXDUB_RAM_TRONG_GB" in w, "worker không đọc biến môi trường"
    assert "--ram-trong-gb" in w, (
        "vẫn phải nhận tham số cũ: cha bản 3.14.1-3.16.0 đang gửi nó")


def test_worker_KHONG_CHET_khi_gap_tham_so_la():
    """Cha bản mới hơn gửi tham số worker chưa biết thì bỏ qua, không chết —
    người dùng không có cách nào tự chữa một lỗi như vậy."""
    w = open(WORKER, encoding="utf-8").read()
    assert "parse_known_args" in w, "còn dùng parse_args là còn chết vì tham số lạ"
    assert "Bỏ qua tham số không nhận ra" in w, "bỏ qua thì phải NÓI RA"


# ------------------ câu lỗi phải nói việc thật phải làm ------------------

def test_het_RAM_khong_con_ra_hop_thoai_loi_ngoai_du_tinh():
    """Hộp thoại chủ dự án nhận được chỉ nói "Có lỗi ngoài dự tính" vì không
    mục nào trong bảng lời khuyên khớp `mkl_malloc`."""
    from autodub_gui.dub_constants import friendly_error

    for cau_loi in (
        "Whisper worker báo lỗi: {'error': \"Không nạp được model Whisper "
        "'medium': mkl_malloc: failed to allocate memory\"}",
        "Máy không đủ bộ nhớ cho bất kỳ model nào (đã thử: medium, small)",
    ):
        ket = friendly_error(cau_loi)
        assert ket is not None, f"chưa có lời khuyên cho: {cau_loi[:60]}"
        tieu_de, viec_can_lam = ket
        assert "bộ nhớ" in tieu_de.lower()
        assert "Độ chính xác" in viec_can_lam, "không chỉ ra nút cần bấm"
        assert "không bị trừ Vox" in viec_can_lam.replace("Vox lần nữa", "Vox")


def test_het_RAM_may_KHAC_het_bo_nho_card_do_hoa():
    """Hai chỗ khác nhau, cách chữa khác nhau — gộp làm một là chỉ sai đường."""
    from autodub_gui.dub_constants import friendly_error

    ram = friendly_error("mkl_malloc: failed to allocate memory")
    card = friendly_error("CUDA failed with error out of memory")
    assert ram is not None and card is not None
    assert ram[0] != card[0]


def test_loi_card_do_hoa_bat_dung_cau_THAT_cua_ctranslate2():
    """Nhật ký thật của chủ dự án ghi "CUDA failed with error out of memory",
    còn bảng lời khuyên chỉ bắt "CUDA out of memory" — nên mục đó chưa từng
    khớp một lần nào kể từ khi được viết."""
    from autodub_gui.dub_constants import friendly_error

    assert friendly_error("GPU float16 thất bại (CUDA failed with error out "
                          "of memory)") is not None
