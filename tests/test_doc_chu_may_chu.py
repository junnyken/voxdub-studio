"""mini-spec H2b — đọc lại chữ overlay bằng mô hình nhìn ảnh trên máy chủ.

Bug gốc: OCR tại máy đọc tiếng Việt MẤT DẤU ("Đăng ký kênh" → "Dang ky kenh")
mà confidence vẫn 0,84-0,99. Bộ test này canh hai chuyện dễ hỏng nhất:
  1. KHÔNG gửi thừa khung lên máy chủ (tiền thật, ~1.150 token mỗi khung);
  2. ánh xạ khung↔chữ không được lệch — lệch một khung là sai dòng thời gian
     của mọi khung sau đó, và không có tín hiệu nào để phát hiện.
"""
import pytest

from autodub.media import doc_chu_may_chu as dcmc
from autodub.media.text_regions import QuanSatChu


def _qs(frame, text, *, y=0.8, x=0.1, conf=0.95):
    return QuanSatChu(text=text, confidence=conf, x=x, y=y, w=0.5, h=0.1,
                      frame_index=frame, timestamp_s=frame * 0.2,
                      source="in_process", status="ok")


# --- chia đoạn: nền tảng của việc tiết kiệm -------------------------------

def test_khung_lien_tiep_cung_chu_gop_thanh_mot_doan():
    quan_sat = [_qs(0, "Xin loi"), _qs(1, "Xin loi"), _qs(2, "Xin loi")]
    assert dcmc.chia_doan(quan_sat) == [[0, 1, 2]]


def test_chu_doi_thi_sang_doan_moi():
    quan_sat = [_qs(0, "Xin loi"), _qs(1, "Xin loi"), _qs(2, "Cam on")]
    assert dcmc.chia_doan(quan_sat) == [[0, 1], [2]]


def test_cung_chu_nhung_KHONG_lien_ke_thi_tach_hai_doan():
    # Caption hiện, biến mất, rồi hiện lại là HAI lần hiện khác nhau trên
    # dòng thời gian. Gộp lại là bịa ra một khoảng liên tục không có thật.
    quan_sat = [_qs(0, "Mua ngay"), _qs(5, "Mua ngay")]
    assert dcmc.chia_doan(quan_sat) == [[0], [5]]


def test_khung_khong_co_chu_khong_thuoc_doan_nao():
    quan_sat = [_qs(0, "A"), _qs(1, "   "), _qs(2, "A")]
    # Khung 1 rỗng nghĩa ⇒ cắt mạch, khung 2 là lần hiện MỚI.
    assert dcmc.chia_doan(quan_sat) == [[0], [2]]


def test_nhieu_vung_chu_trong_mot_khung_gop_theo_thu_tu_doc():
    # Hai dòng phụ đề song ngữ: thứ tự trên→dưới phải ổn định, nếu không thì
    # hai khung giống hệt nhau lại bị coi là khác nhau và gửi đi hai lần.
    a = [_qs(0, "Excuse me", y=0.70), _qs(0, "Xin loi", y=0.85)]
    b = [_qs(1, "Xin loi", y=0.85), _qs(1, "Excuse me", y=0.70)]
    assert dcmc.chia_doan(a + b) == [[0, 1]]


# --- gọi máy chủ: gửi đúng số khung cần thiết ------------------------------

class _ClientGia:
    def __init__(self, tra_ve=None):
        self.luot = []
        self._tra_ve = tra_ve or {}

    def assist(self, task, input_data, *, job_id, images=None, **kw):
        self.luot.append({"task": task, "input": input_data,
                          "so_anh": len(images or [])})
        return self._tra_ve.get(len(self.luot), [])


def test_chi_gui_MOT_khung_dai_dien_cho_moi_doan(tmp_path, monkeypatch):
    anh = []
    for i in range(6):
        p = tmp_path / f"k{i}.png"
        _anh_gia(p)
        anh.append(str(p))
    # 6 khung nhưng chỉ 2 đoạn chữ ⇒ chỉ được gửi 2 ảnh, không phải 6.
    quan_sat = [_qs(i, "AAA") for i in range(3)] + [_qs(i, "BBB") for i in range(3, 6)]
    client = _ClientGia({1: [{"anh": 1, "dong": ["Đoạn một"]},
                             {"anh": 2, "dong": ["Đoạn hai"]}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, anh, client=client)

    assert len(client.luot) == 1, "phải gộp vào đúng một lượt gọi"
    assert client.luot[0]["so_anh"] == 2, "chỉ gửi khung đại diện của mỗi đoạn"
    assert client.luot[0]["input"] == {"soAnh": 2}
    assert client.luot[0]["task"] == "doc_chu_khung_hinh"
    assert [q.text for q in ra[:3]] == ["Đoạn một"] * 3
    assert [q.text for q in ra[3:]] == ["Đoạn hai"] * 3


def test_ket_qua_doc_dung_ap_cho_CA_doan_va_giu_nguyen_moc_thoi_gian(tmp_path):
    anh = []
    for i in range(3):
        p = tmp_path / f"k{i}.png"
        _anh_gia(p)
        anh.append(str(p))
    quan_sat = [_qs(i, "Dang ky kenh") for i in range(3)]
    client = _ClientGia({1: [{"anh": 1, "dong": ["Đăng ký kênh"]}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, anh, client=client)

    assert [q.text for q in ra] == ["Đăng ký kênh"] * 3
    assert [q.timestamp_s for q in ra] == [0.0, 0.2, 0.4]
    assert all(q.source == "may_chu" for q in ra)


def test_khong_bia_diem_tin_cay_cho_ban_doc_may_chu(tmp_path):
    p = tmp_path / "k0.png"
    _anh_gia(p)
    quan_sat = [_qs(0, "Xin loi")]
    client = _ClientGia({1: [{"anh": 1, "dong": ["Xin lỗi"]}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, [str(p)], client=client)
    # Mô hình không chấm điểm tin cậy. Điền 1.0 cho đủ chỗ thì trông y hệt
    # một điểm đo thật, và mọi thứ đọc trường này sau đó đều tin nhầm.
    assert ra[0].confidence is None


def test_chia_lo_khi_nhieu_doan_hon_tran_moi_luot(tmp_path):
    anh = []
    for i in range(8):
        p = tmp_path / f"k{i}.png"
        _anh_gia(p)
        anh.append(str(p))
    quan_sat = [_qs(i, f"chu {i}") for i in range(8)]  # 8 đoạn khác nhau
    client = _ClientGia()
    dcmc.doc_lai_bang_may_chu(quan_sat, anh, client=client)
    assert [l["so_anh"] for l in client.luot] == [6, 2], \
        "phải chia đúng theo trần 6 ảnh mỗi lượt của máy chủ"


# --- hỏng thì lui về bản cục bộ, KHÔNG giết cả lượt phân tích -------------

def test_may_chu_hong_thi_giu_nguyen_ban_doc_cuc_bo(tmp_path):
    p = tmp_path / "k0.png"
    _anh_gia(p)
    quan_sat = [_qs(0, "Dang ky kenh")]

    class _Hong:
        def assist(self, *a, **kw):
            raise RuntimeError("mạng lỗi")

    ra = dcmc.doc_lai_bang_may_chu(quan_sat, [str(p)], client=_Hong())
    assert [q.text for q in ra] == ["Dang ky kenh"]
    assert ra[0].source == "in_process", "không được đánh dấu là đọc từ máy chủ"


def test_chua_cau_hinh_may_chu_thi_khong_goi_gi_ca(tmp_path, monkeypatch):
    p = tmp_path / "k0.png"
    _anh_gia(p)
    from autodub import saas_client
    monkeypatch.setattr(saas_client, "is_configured", lambda: False)
    quan_sat = [_qs(0, "Dang ky")]
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, [str(p)])
    assert [q.text for q in ra] == ["Dang ky"]


def test_may_chu_doc_ra_khung_khong_chu_thi_bo_han_khung_do(tmp_path):
    # Máy chủ nói "khung này không có chữ" thì tin máy chủ, KHÔNG giữ lại bản
    # đọc sai của OCR cục bộ (thường là rác nhận nhầm từ hoa văn nền).
    p = tmp_path / "k0.png"
    _anh_gia(p)
    quan_sat = [_qs(0, "l1I")]
    client = _ClientGia({1: [{"anh": 1, "dong": []}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, [str(p)], client=client)
    assert ra == []


def test_doan_may_chu_khong_tra_loi_thi_giu_ban_cuc_bo_cua_rieng_doan_do(tmp_path):
    anh = []
    for i in range(2):
        p = tmp_path / f"k{i}.png"
        _anh_gia(p)
        anh.append(str(p))
    quan_sat = [_qs(0, "AAA"), _qs(1, "BBB")]
    # Máy chủ chỉ trả lời ảnh 1, bỏ ảnh 2.
    client = _ClientGia({1: [{"anh": 1, "dong": ["Đoạn một"]}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, anh, client=client)
    theo_khung = {q.frame_index: q.text for q in ra}
    assert theo_khung[0] == "Đoạn một"
    assert theo_khung[1] == "BBB", "đoạn không có trả lời phải giữ bản cục bộ"


def test_giu_dung_thu_tu_dong_tren_duoi_cua_phu_de_song_ngu(tmp_path):
    # Lỗi thật của chính bản dựng đầu: bước sắp xếp cuối xếp theo CHỮ CÁI nên
    # "Excuse me" nhảy lên trước "Xin lỗi" ở khung này nhưng không ở khung
    # khác — thứ tự đọc trên→dưới của phụ đề song ngữ bị đảo lung tung.
    p = tmp_path / "k0.png"
    _anh_gia(p)
    quan_sat = [_qs(0, "Excuse me", y=0.70), _qs(0, "Xin loi", y=0.85)]
    client = _ClientGia({1: [{"anh": 1, "dong": ["Xin lỗi", "Excuse me"]}]})
    ra = dcmc.doc_lai_bang_may_chu(quan_sat, [str(p)], client=client)
    assert [q.text for q in ra] == ["Xin lỗi", "Excuse me"], \
        "phải giữ đúng thứ tự máy chủ trả về, không xếp lại theo chữ cái"


def test_khong_co_chu_nao_thi_khong_goi_may_chu(tmp_path):
    client = _ClientGia()
    ra = dcmc.doc_lai_bang_may_chu([], [], client=client)
    assert ra == []
    assert client.luot == []


def _anh_gia(duong_dan):
    from PIL import Image
    Image.new("RGB", (64, 32), "white").save(duong_dan)


# --- chỗ cắm bộ đọc ở text_regions ----------------------------------------

def test_bo_doc_khong_hop_le_bao_loi_ngay():
    from autodub.media import text_regions as tr
    with pytest.raises(ValueError, match="Bộ đọc không hợp lệ"):
        tr.read_text_regions(["a.png"], bo_doc="linh tinh")


def test_mac_dinh_van_la_bo_doc_cuc_bo():
    # Đổi mặc định là đổi hành vi của mọi nơi gọi cũ (và bắt đầu tiêu Vox mà
    # không ai yêu cầu) — phải là quyết định có chủ đích, không phải trôi.
    import inspect
    from autodub.media import text_regions as tr
    tham_so = inspect.signature(tr.read_text_regions).parameters
    assert tham_so["bo_doc"].default == tr.BO_DOC_CUC_BO
