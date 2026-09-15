"""D5 — worker phải TỰ KHAI mã nguồn nó đang chạy.

Trước lát này `/health` của worker trả đúng chuỗi ``"ok"``. Hậu quả đo được:
chốt ``--sha-nguon`` của ``scripts/trien_khai_vibehost.py`` **phải bỏ trống**
cho worker (workflow đã ghi chú đúng chuyện đó), nên không ai kiểm được worker
đang chạy mã nào — và nó đã từng chạy mã trước C53 nhiều ngày mà không ai hay.

Ngày 15/09 lại đúng chuyện ấy: nhánh deploy worker ở ``6baf2f2`` trong khi bản
đang chạy sinh từ ``bd62f3f``, và **không cách nào phát hiện từ xa**.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUONG_WORKER = os.path.join(GOC, "control_server", "worker-dub", "dub_worker.py")


@pytest.fixture(scope="module")
def worker():
    spec = importlib.util.spec_from_file_location("dub_worker_d5", DUONG_WORKER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dub_worker_d5"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------- đọc SHA ---

def test_khong_co_tep_thi_IM_LANG_tra_None(worker, monkeypatch, capsys):
    """Chạy từ mã nguồn / chạy test là ca BÌNH THƯỜNG — không được kêu."""
    monkeypatch.delenv("APP_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    assert worker.doc_sha_nguon() is None
    assert capsys.readouterr().out == "", "ca bình thường mà vẫn xả log"


def test_bien_moi_truong_duoc_uu_tien(worker, monkeypatch):
    monkeypatch.setenv("APP_COMMIT", "a" * 40)
    assert worker.doc_sha_nguon() == "a" * 12


def test_doc_tu_tep_SOURCE_SHA_canh_ben(worker, monkeypatch, tmp_path):
    monkeypatch.delenv("APP_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    tep = tmp_path / "SOURCE_SHA"
    tep.write_text("6baf2f2d46caea63f32a069be9bdd63eb4982dd6\n", encoding="utf-8")
    monkeypatch.setattr(worker, "__file__", str(tmp_path / "dub_worker.py"))
    assert worker.doc_sha_nguon() == "6baf2f2d46ca"


def test_cat_dung_12_ky_tu_nhu_control_server(worker, monkeypatch):
    """Cắt 12 ký tự y như `control_server/src/version.js` — hai bên lệch cách
    cắt thì `_sha_lech()` so tiền tố sẽ ra kết quả khó hiểu."""
    monkeypatch.setenv("APP_COMMIT", "0123456789abcdef" * 2)
    assert len(worker.doc_sha_nguon()) == 12


# ------------------------------------------------- thân /health ---

def _than(worker) -> dict:
    """Dựng lại đúng thân mà `_HealthHandler.do_GET` ghi ra, không giả lập."""
    ghi = {}

    class GiaHandler(worker._HealthHandler):
        def __init__(self):            # bỏ qua __init__ của BaseHTTPRequestHandler
            pass

        def send_response(self, ma): ghi["ma"] = ma
        def send_header(self, k, v): ghi.setdefault("dau", {})[k] = v
        def end_headers(self): pass

        @property
        def wfile(self):
            class W:
                @staticmethod
                def write(b): ghi["than"] = b
            return W()

    GiaHandler().do_GET()
    return ghi


def test_health_tra_JSON_va_van_la_200(worker, monkeypatch):
    monkeypatch.setenv("APP_COMMIT", "b" * 40)
    ghi = _than(worker)
    assert ghi["ma"] == 200, "nền tảng hosting chấm sống/chết bằng mã 200"
    d = json.loads(ghi["than"].decode("utf-8"))
    assert d["ok"] is True
    assert d["commit"] == "b" * 12


def test_khong_co_SHA_thi_BO_HAN_truong_commit(worker, monkeypatch):
    """Không đoán. `_sha_lech()` coi `commit` rỗng là «chưa xác minh được»,
    nên khai một chuỗi rỗng/giả còn tệ hơn là không khai."""
    monkeypatch.delenv("APP_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    d = json.loads(_than(worker)["than"].decode("utf-8"))
    assert d["ok"] is True
    assert "commit" not in d


def test_Content_Length_khop_than(worker, monkeypatch):
    """Sai Content-Length thì client treo chờ byte không bao giờ tới."""
    monkeypatch.setenv("APP_COMMIT", "c" * 40)
    ghi = _than(worker)
    assert int(ghi["dau"]["Content-Length"]) == len(ghi["than"])


# --------------------------------- khớp với bên đọc nó (D3) ---

def test_thay_doi_nay_KHONG_lam_do_luot_deploy(worker, monkeypatch):
    """Chốt chống-sửa-quá-tay: `_phu_thuoc_hong()` nay sẽ parse được JSON của
    worker. Nó chỉ soi trường `db`; worker không có trường đó nên phải trả
    None, tức KHÔNG biến thay đổi này thành một lượt deploy đỏ."""
    sys.path.insert(0, os.path.join(GOC, "scripts"))
    try:
        import trien_khai_vibehost as tkv
    finally:
        sys.path.pop(0)
    monkeypatch.setenv("APP_COMMIT", "d" * 40)
    than = _than(worker)["than"].decode("utf-8")
    assert tkv._phu_thuoc_hong(than) is None


def test_sha_lech_NAY_da_doc_duoc_worker(worker, monkeypatch):
    """Trước lát này `_sha_lech()` trả «không trả JSON nên không khai được
    SHA» cho worker. Giờ nó phải kiểm được thật — cả chiều đúng lẫn chiều sai."""
    sys.path.insert(0, os.path.join(GOC, "scripts"))
    try:
        import trien_khai_vibehost as tkv
    finally:
        sys.path.pop(0)
    monkeypatch.setenv("APP_COMMIT", "e" * 40)
    than = _than(worker)["than"].decode("utf-8")
    assert tkv._sha_lech(than, "e" * 40) is None
    assert tkv._sha_lech(than, "f" * 40) is not None


# ==================================================================
# Tệp có trong build context ≠ tệp vào được trong ẢNH
# ==================================================================

def test_DOCKERFILE_SINH_RA_phai_chep_SOURCE_SHA_vao_anh(tmp_path):
    """Đo thật 15/09: lượt deploy đầu tiên sau khi thêm chốt, worker trả
    ``{"ok": true}`` KHÔNG kèm ``commit``.

    Nguyên nhân: `SOURCE_SHA` được ghi vào build context nhưng Dockerfile chỉ
    có ``COPY dub_worker.py /app/dub_worker.py`` — tệp không bao giờ vào ảnh,
    nên `doc_sha_nguon()` tìm cạnh `/app/dub_worker.py` không thấy gì.

    Đây đúng cái bẫy `control_server/src/version.js` đã ghi chú: tệp phải nằm
    trong thứ lệnh COPY **thật sự mang đi**; có mặt trong context là CHƯA ĐỦ.

    Test này đọc Dockerfile **do script sinh ra**, không đọc bản trên main —
    vì bản trên main cố ý KHÔNG có dòng đó (gốc repo không có tệp SOURCE_SHA
    nào, một dòng COPY cứng ở đó sẽ làm hỏng mọi lượt dựng từ main).
    """
    import re
    import subprocess

    kich_ban = os.path.join(GOC, "scripts", "gen_vays_dub_worker_branch.sh")
    noi_dung = open(kich_ban, encoding="utf-8").read()

    # Bóc đúng phần THAY THẾ của lệnh sed dựng Dockerfile.
    m = re.search(r"sed -e 's#\^COPY control_server/worker-dub/dub_worker[^#]*#([^#]*)#'",
                  noi_dung)
    assert m, "không tìm thấy lệnh sed dựng Dockerfile cho nhánh deploy"
    thay_the = m.group(1)
    assert "COPY SOURCE_SHA" in thay_the, (
        "Dockerfile sinh ra không chép SOURCE_SHA vào ảnh ⇒ worker sẽ không "
        "khai được `commit`, và chốt --sha-nguon sẽ làm ĐỎ mọi lượt deploy "
        f"worker. Phần thay thế hiện tại: {thay_the!r}")

    # Và nó phải vào ĐÚNG chỗ `doc_sha_nguon()` đi tìm: cạnh dub_worker.py.
    dich_worker = re.search(r"COPY dub_worker\.py (\S+)", thay_the).group(1)
    dich_sha = re.search(r"COPY SOURCE_SHA (\S+)", thay_the).group(1)
    assert os.path.dirname(dich_sha) == os.path.dirname(dich_worker), (
        f"SOURCE_SHA vào {dich_sha} nhưng dub_worker.py ở {dich_worker} — "
        "`doc_sha_nguon()` tìm cạnh chính nó nên sẽ không thấy")
