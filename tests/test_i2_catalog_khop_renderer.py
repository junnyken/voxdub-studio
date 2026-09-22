"""Từ điển chỉ đạo hình ảnh v1 phải KHỚP thứ khâu ghép hình làm được — I2.

Catalog nằm ở máy chủ (`control_server/src/data/visual-direction-catalog.json`)
còn khâu dựng hình nằm ở Python (`autodub/product_video.py`). Hai bên hai
ngôn ngữ, hai lượt phát hành — đúng hình dạng của mọi lần "trôi lệch âm thầm"
mà dự án này đã dính: `dub-langs` (V49), tốc độ đọc của H6, mã thành công
`201` của Phase H. Cả ba lần đều xanh ở từng phía và hỏng ở ĐƯỜNG NỐI.

Nên tệp này đọc THẲNG tệp JSON của máy chủ rồi đối chiếu với chính mã Python:

* mục nào khai `supported` thì hàm dựng hình đó phải CÓ THẬT, nhận đúng tham
  số đó, và giá trị tham số phải nằm trong bảng kiểu chuyển cảnh thật;
* chuỗi lệnh ffmpeg sinh ra phải đúng thứ mục đó hứa (cắt thẳng thì không
  được có `xfade`, mờ chồng thì phải là `fade`, tan dần phải là `dissolve`);
* cảnh CUỐI không được ngắn đi vì chuyển cảnh — đây là đúng cái lỗi "mấy giây
  cuối đứng hình" của D1/H4c-1;
* khâu ghép hình chưa có zoom/pan/chỉnh màu thì catalog không được khai là
  làm được.

Chiều kiểm là **catalog hứa ⇒ mã phải có**. Thêm khả năng mới vào
`product_video.py` thì test này KHÔNG đỏ; chỉ khi catalog hứa quá tay, hoặc
khi một khả năng đang được hứa bị gỡ khỏi mã, nó mới đỏ.
"""
from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from autodub.product_video import KIEU_CHUYEN, _lenh_ghep, ghep_anh_nguoi_dung

GOC = pathlib.Path(__file__).resolve().parent.parent
TEP_CATALOG = (GOC / "control_server" / "src" / "data"
               / "visual-direction-catalog.json")
MA_RENDERER = (GOC / "autodub" / "product_video.py").read_text(encoding="utf-8")

#: Tham số mang nghĩa thời gian — catalog bị cấm chạm vào, vì thời lượng cảnh
#: chỉ có MỘT nguồn: giọng đọc thật (`du_an_tu_kich_ban._moc_that`, D1).
THAM_SO_CAM = {"giay", "giay_moi_anh", "giay_chuyen", "thoi_luong", "dai_tieng",
               "duration", "offset", "start", "end", "speed", "fps"}


@pytest.fixture(scope="module")
def catalog() -> dict:
    if not TEP_CATALOG.is_file():
        pytest.skip("không có control_server/ (nhánh deploy chỉ chứa autodub)")
    return json.loads(TEP_CATALOG.read_text(encoding="utf-8"))


def _moi_muc(catalog: dict):
    for nhom in catalog["groups"]:
        for muc in nhom["values"]:
            yield nhom["id"], muc


def _ham_cua(implementation: str):
    """`product_video.ghep_anh_nguoi_dung` → chính hàm đó, hoặc None."""
    mo_dun, _, ten = implementation.partition(".")
    if mo_dun != "product_video":
        return None
    return {"ghep_anh_nguoi_dung": ghep_anh_nguoi_dung}.get(ten)


def _thoi_luong_dau_vao(lenh: list[str]) -> list[float]:
    """Các giá trị `-t` trong lệnh ffmpeg, theo đúng thứ tự ảnh."""
    return [float(lenh[i + 1]) for i, x in enumerate(lenh) if x == "-t"]


# --------------------------------------------------------- catalog ⇄ mã ---

def test_moi_kieu_chuyen_canh_CO_THAT_deu_co_mat_trong_catalog(catalog):
    """Chiều NGƯỢC lại: mã có kiểu nào thì catalog phải khai kiểu đó.

    v1 cố ý chỉ ship 3/6 kiểu (bám danh sách mini-spec I2 cho phép). v2 mở
    hết, nên từ nay hai bên phải bằng nhau — thêm một kiểu vào `KIEU_CHUYEN`
    mà quên catalog thì người dùng không bao giờ thấy nó, và không ai biết vì
    sao. Muốn giữ một kiểu ở ngoài catalog thì phải sửa test này, tức là phải
    nói ra lý do.
    """
    trong_catalog = {
        m["h4_mapping"]["parameters"]["kieu_chuyen"]
        for nhom, m in _moi_muc(catalog)
        if nhom == "transition" and m["render_mode"] == "supported"}
    assert trong_catalog == set(KIEU_CHUYEN), (
        f"catalog khai {sorted(trong_catalog)} còn mã có {sorted(KIEU_CHUYEN)}")


def test_moi_muc_supported_tro_vao_ham_CO_THAT(catalog):
    thay = 0
    for nhom, muc in _moi_muc(catalog):
        if muc["render_mode"] != "supported":
            continue
        thay += 1
        ham = _ham_cua(muc["h4_mapping"]["implementation"])
        assert ham is not None, (
            f"{nhom}.{muc['id']} trỏ vào «{muc['h4_mapping']['implementation']}» "
            "— không có hàm nào như vậy trong autodub/product_video.py")
    assert thay, "catalog không có mục supported nào — đọc nhầm tệp?"


def test_tham_so_cua_mapping_la_tham_so_ham_do_THAT_SU_NHAN(catalog):
    for nhom, muc in _moi_muc(catalog):
        if muc["render_mode"] != "supported":
            continue
        ham = _ham_cua(muc["h4_mapping"]["implementation"])
        nhan = set(inspect.signature(ham).parameters)
        for khoa in muc["h4_mapping"]["parameters"]:
            assert khoa in nhan, (
                f"{nhom}.{muc['id']}: {ham.__name__}() không nhận tham số "
                f"«{khoa}» — mapping này gọi lên là ném TypeError")


def test_kieu_chuyen_trong_catalog_deu_co_trong_bang_kieu_THAT(catalog):
    dung = [m for _, m in _moi_muc(catalog)
            if m["render_mode"] == "supported"
            and "kieu_chuyen" in m["h4_mapping"]["parameters"]]
    assert dung, "không mục nào khai kiểu chuyển cảnh — đọc nhầm nhóm?"
    for muc in dung:
        kieu = muc["h4_mapping"]["parameters"]["kieu_chuyen"]
        assert kieu in KIEU_CHUYEN, (
            f"{muc['id']}: «{kieu}» không còn trong KIEU_CHUYEN. Gỡ một kiểu "
            "khỏi mã mà quên catalog = người dùng chọn xong thì ffmpeg ném lỗi")


# ------------------------------------------ lệnh sinh ra đúng thứ đã hứa ---

def test_cat_thang_KHONG_sinh_xfade(catalog):
    muc = next(m for _, m in _moi_muc(catalog) if m["id"] == "cat_thang")
    lenh = " ".join(_lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4",
                               [2.0, 1.5, 3.0], 0.3,
                               muc["h4_mapping"]["parameters"]["kieu_chuyen"]))
    assert "xfade" not in lenh, "«cắt thẳng» mà vẫn hoà hình là nói sai"
    assert "concat=n=3" in lenh


@pytest.mark.parametrize("ma_muc,ten_ffmpeg", [("fade_nhe", "fade"),
                                               ("crossfade_ngan", "dissolve"),
                                               ("truot_trai", "slideleft"),
                                               ("truot_len", "slideup"),
                                               ("mo_vong", "circleopen")])
def test_chuyen_canh_sinh_dung_bo_loc_ffmpeg(catalog, ma_muc, ten_ffmpeg):
    muc = next(m for _, m in _moi_muc(catalog) if m["id"] == ma_muc)
    lenh = " ".join(_lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4",
                               [2.0, 1.5, 3.0], 0.3,
                               muc["h4_mapping"]["parameters"]["kieu_chuyen"]))
    assert f"xfade=transition={ten_ffmpeg}" in lenh, (
        f"{ma_muc} hứa «{muc['label_vi']}» nhưng lệnh ra không dùng "
        f"{ten_ffmpeg} — nhãn và thứ chạy thật lệch nhau")


@pytest.mark.parametrize("ma_muc", ["cat_thang", "fade_nhe", "crossfade_ngan",
                                   "truot_trai", "truot_len", "mo_vong"])
def test_canh_CUOI_khong_bi_chuyen_canh_an_mat(catalog, ma_muc):
    """Cảnh cuối phải giữ nguyên trọn thời lượng của nó.

    D1 kéo cảnh cuối tới hết tệp tiếng đúng vì "cuối câu cuối KHÔNG phải cuối
    dòng thời gian". Một kiểu chuyển cảnh rút ngắn cảnh cuối sẽ dựng lại đúng
    cái đuôi mất hình đã sửa ngày 21/09.
    """
    muc = next(m for _, m in _moi_muc(catalog) if m["id"] == ma_muc)
    kieu = muc["h4_mapping"]["parameters"]["kieu_chuyen"]
    giay = [2.0, 1.5, 3.0, 2.2, 4.1]          # 5 cảnh, dài ngắn khác nhau
    gc = 0.3
    lenh = _lenh_ghep([f"a{i}.png" for i in range(5)], "ra.mp4", giay, gc, kieu)
    vao = _thoi_luong_dau_vao(lenh)

    assert vao[-1] == pytest.approx(giay[-1], abs=1e-3), (
        f"{ma_muc}: cảnh cuối vào ffmpeg với {vao[-1]}s trong khi lời đọc của "
        f"nó dài {giay[-1]}s")

    # Dòng thời gian sau khi trừ phần chồng lấn phải đúng bằng tổng lời đọc.
    chong_lan = gc * (len(giay) - 1) if KIEU_CHUYEN[kieu][1] else 0.0
    assert sum(vao) - chong_lan == pytest.approx(sum(giay), abs=1e-3), (
        f"{ma_muc}: tổng dòng thời gian {sum(vao) - chong_lan:.3f}s ≠ tổng lời "
        f"đọc {sum(giay):.3f}s — video sẽ lệch dần so với tiếng")


# ------------------------------------------- không hứa thứ mã chưa có ---

def test_khong_khai_zoom_pan_khi_khau_ghep_hinh_chua_co(catalog):
    if "zoompan" in MA_RENDERER:
        pytest.skip("khâu ghép hình nay có zoompan — cập nhật nhóm motion của "
                    "catalog rồi sửa test này")
    mo_ta_dong = " ".join(
        f"{m['id']} {m['label_vi']} {m['prompt_hint_vi']}"
        for nhom, m in _moi_muc(catalog)
        if nhom == "motion" and m["render_mode"] == "supported").lower()
    for tu in ("zoom", "pan ", "ken burns", "lia", "di chuyển"):
        assert tu not in mo_ta_dong, (
            f"nhóm motion khai «{tu}» là supported trong khi _lenh_ghep() chỉ "
            "có scale/pad/xfade — không có bộ lọc chuyển động nào")


def test_khong_hua_chinh_mau_khi_khau_ghep_hinh_chua_co(catalog):
    co_chinh_mau = any(t in MA_RENDERER
                       for t in ("eq=brightness", "curves=", "colorchannelmixer",
                                 "colorbalance"))
    if co_chinh_mau:
        pytest.skip("khâu ghép hình nay chỉnh được màu — cập nhật nhóm "
                    "lighting_color rồi sửa test này")
    for nhom, muc in _moi_muc(catalog):
        if nhom != "lighting_color":
            continue
        assert muc["render_mode"] == "advisory_only", (
            f"lighting_color.{muc['id']} khai supported nhưng khâu ghép hình "
            "không có bước chỉnh màu nào — ảnh vào sao thì ra vậy")


def test_dem_trang_cua_anh_lech_ti_le_van_duoc_noi_ra(catalog):
    """Ảnh không đúng 9:16 bị ĐỆM TRẮNG. Catalog phải nói, không giấu."""
    assert "color=white" in MA_RENDERER, (
        "màu đệm đổi rồi — sửa lại câu chữ trong nhóm composition/"
        "lighting_color của catalog cho khớp")
    nhom_bo_cuc = next(g for g in catalog["groups"] if g["id"] == "composition")
    assert "trắng" in nhom_bo_cuc["description_vi"].lower(), (
        "người dùng chọn tông tối mà không ai báo hai dải trắng hai bên thì "
        "họ chỉ phát hiện sau khi xuất video")


# ----------------------------------------------- catalog không đụng D1 ---

def test_KHONG_mapping_nao_mang_tham_so_thoi_gian(catalog):
    for nhom, muc in _moi_muc(catalog):
        map_ = muc.get("h4_mapping")
        if not map_:
            continue
        cham = THAM_SO_CAM & set(map_["parameters"])
        assert not cham, (
            f"{nhom}.{muc['id']} mang tham số thời gian {sorted(cham)} — thời "
            "lượng cảnh do giọng đọc thật quyết định (D1), catalog không có "
            "quyền đổi")


def test_nhom_pacing_chi_la_goi_y_va_khai_ro_nguon_thoi_luong(catalog):
    nhom_nhip = next(g for g in catalog["groups"] if g["id"] == "pacing")
    assert nhom_nhip["values"], "nhóm pacing rỗng"
    for muc in nhom_nhip["values"]:
        assert muc["render_mode"] == "advisory_only", (
            f"pacing.{muc['id']}: nhịp dựng mà thành lệnh thì nó sẽ đòi đổi "
            "thời lượng — thứ D1 vừa dựng lại theo tiếng thật")
        assert muc["h4_mapping"] is None
        assert muc["nguon_thoi_luong"] == "d1_audio"
