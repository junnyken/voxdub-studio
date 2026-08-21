'use strict'

/**
 * C2 — chốt chuyển pha cho tính năng dựng ảnh sản phẩm.
 *
 * Lớp lỗi cần chặn ở đây không kêu tiếng nào khi sai: mở nhầm cho người bán
 * thật trong lúc phán quyết chưa được hiệu chỉnh. Mọi thứ vẫn chạy, vẫn trả
 * ảnh, vẫn thu tiền — hậu quả chỉ hiện ra ở tài khoản TikTok của họ vài tuần
 * sau. Nên mặc định phải là ĐÓNG, và mọi đường không rõ ràng cũng phải là
 * đóng.
 */
const test = require('node:test')
const assert = require('node:assert')

const stage = require('../src/services/image-stage.service')
const { DEFAULTS } = require('../src/services/config.service')
const stats = require('../src/services/assist-stats.service')

// -- Mặc định phải đóng ------------------------------------------------------

test('mặc định là TẮT, không phải bật', () => {
  assert.equal(DEFAULTS['image.scene.stage'], 'off')
})

test('danh sách máy hiệu chỉnh mặc định RỖNG', () => {
  // Mặc định "mọi máy" thì nấc hiệu chỉnh chẳng chặn được ai.
  assert.equal(DEFAULTS['image.scene.calibration.devices'], '')
})

test('nấc tắt thì không máy nào gọi được', () => {
  const r = stage.quyetDinh({ stage: 'off', fingerprint: 'may-1' })
  assert.equal(r.choPhep, false)
  assert.equal(r.code, 'IMAGE_STAGE_OFF')
})

test('gõ sai tên nấc thì ĐÓNG, không phải mở', () => {
  // Một lỗi chính tả trong trang quản trị không được phép mở cửa.
  for (const sai of ['produciton', 'PRODUCTION ', 'true', '1', '', null, undefined]) {
    assert.equal(stage.quyetDinh({ stage: sai, fingerprint: 'may-1' }).choPhep,
      false, `nấc "${sai}" không được mở cửa`)
  }
})

// -- Nấc hiệu chỉnh ----------------------------------------------------------

test('hiệu chỉnh: chỉ máy trong danh sách mới chạy được', () => {
  const co = stage.quyetDinh({
    stage: 'calibration', devices: 'may-1, may-2', fingerprint: 'may-2' })
  assert.equal(co.choPhep, true)
  assert.equal(co.runMode, 'calibration')

  const khong = stage.quyetDinh({
    stage: 'calibration', devices: 'may-1, may-2', fingerprint: 'may-9' })
  assert.equal(khong.choPhep, false)
  assert.equal(khong.code, 'IMAGE_STAGE_CALIBRATION')
})

test('hiệu chỉnh mà danh sách rỗng thì KHÔNG ai chạy được', () => {
  assert.equal(stage.quyetDinh({
    stage: 'calibration', devices: '', fingerprint: 'may-1' }).choPhep, false)
})

test('danh sách chịu được xuống dòng và khoảng trắng thừa', () => {
  // Người dán vân tay máy từ nhật ký sẽ dán mỗi dòng một cái.
  assert.deepEqual(stage.danhSachMay(' may-1 ,\n may-2\nmay-3 '),
    ['may-1', 'may-2', 'may-3'])
})

test('khớp vân tay là khớp ĐÚNG CẢ CHUỖI, không phải khớp một phần', () => {
  // 'may-1' không được mở cửa cho 'may-12'.
  assert.equal(stage.quyetDinh({
    stage: 'calibration', devices: 'may-1', fingerprint: 'may-12' }).choPhep,
  false)
})

// -- Nấc chạy thật -----------------------------------------------------------

test('nấc production mở cho mọi máy và ghi sổ đúng chế độ', () => {
  const r = stage.quyetDinh({ stage: 'production', fingerprint: 'ai-cung-duoc' })
  assert.equal(r.choPhep, true)
  assert.equal(r.runMode, 'production')
})

test('không có nấc nào trả runMode do client tự khai', () => {
  // Hàm chỉ nhận stage/devices/fingerprint — không có đường nào cho thân
  // yêu cầu chen vào. Đây là lý do nó nhận tham số rời chứ không nhận
  // nguyên `request.body`.
  const r = stage.quyetDinh({
    stage: 'calibration', devices: 'may-1', fingerprint: 'may-1',
    runMode: 'production', run_mode: 'production',
  })
  assert.equal(r.runMode, 'calibration')
})

// -- Bảng phán quyết ---------------------------------------------------------

test('bảng phán quyết đếm ĐỦ BA kết cục', () => {
  const p = stats.theoPhanQuyet(7)
  const group = p.find((chang) => chang.$group)
  assert.ok(group, 'không thấy chặng $group')
  for (const khoa of ['safe', 'concept', 'chuaKiemDuoc']) {
    assert.ok(group.$group[khoa], `thiếu nhóm «${khoa}»`)
  }
})

test('bảng phán quyết chỉ nhìn tác vụ kiểm bao bì', () => {
  const m = stats.theoPhanQuyet(7)[0].$match
  assert.equal(m.assistTask, 'packaging_check')
  assert.equal(m.action, 'assist')
})

test('bảng phán quyết KHÔNG lọc sẵn status success', () => {
  // Lọc ở đó thì "chưa kiểm được" vĩnh viễn bằng 0 — tức là tự bịt mắt
  // trước đúng nhóm nguy hiểm nhất.
  const m = stats.theoPhanQuyet(7)[0].$match
  assert.equal(m.status, undefined)
})

test('bảng phán quyết tách theo chế độ chạy', () => {
  const group = stats.theoPhanQuyet(7).find((c) => c.$group).$group
  assert.deepEqual(group._id, { $ifNull: ['$runMode', ''] })
})

test('chưa đủ lượt hiệu chỉnh ĐÃ SOI TAY thì chưa được coi là sẵn sàng', () => {
  // C5 siết lại: đếm lượt đã SOI, không phải lượt đã CHẠY. Chạy 100 ảnh mà
  // không ai nhìn thì con số 100 chỉ nói đã tiêu bao nhiêu tiền.
  assert.equal(stats.sanSangXetDuyet(
    [{ runMode: 'calibration', luot: 99, daSoi: 19 }]).du, false)
  assert.equal(stats.sanSangXetDuyet(
    [{ runMode: 'calibration', luot: 20, daSoi: 20 }]).du, true)
})

test('lượt chạy thật KHÔNG tính vào số lượt hiệu chỉnh', () => {
  const r = stats.sanSangXetDuyet([{ runMode: 'production', luot: 500 }])
  assert.equal(r.luot, 0)
  assert.equal(r.du, false)
})

test('chưa có lượt nào thì không nổ', () => {
  assert.equal(stats.sanSangXetDuyet([]).du, false)
  assert.equal(stats.sanSangXetDuyet(undefined).du, false)
})

// -- Cửa có thật sự dùng chốt không -----------------------------------------
//
// `control_server` cố ý chỉ có test thuần (không dựng Mongo), nên đường duy
// nhất kiểm được "route đã nối dây chưa" là đọc chính mã nguồn. Cách này thô
// nhưng bắt đúng lớp lỗi từng xảy ra thật: dịch vụ viết xong, test xanh, mà
// route thì quên gọi.

const h = require('./helpers/doc-ma')

const NGUON = h.ma('src/routes/ai.js')
const thanRoute = (duong) => h.thanHam('src/routes/ai.js', duong)

test('cửa dựng ảnh có gọi chốt chuyển pha', () => {
  assert.match(thanRoute('/product-scene'), /imageStage\.quyetDinh\(/)
})

test('chốt đứng TRƯỚC replay', () => {
  // Cửa đã đóng mà vẫn trả nốt kết quả cũ qua `replay` thì không gọi là
  // đóng — người dùng cứ gửi lại đúng jobId cũ là có ảnh.
  // `truoc()` tự bắt buộc cả hai phải CÓ MẶT rồi mới so thứ tự — `indexOf`
  // trả -1 khi không thấy, và -1 nhỏ hơn mọi vị trí, nên viết tay thì test
  // xanh cả khi chốt bị gỡ sạch (mini-spec C8).
  h.truoc(thanRoute('/product-scene'), 'imageStage.quyetDinh(', 'replay(',
    'replay chạy trước chốt: cửa đóng vẫn phục vụ được kết quả cũ')
})

test('mọi lượt dựng ảnh đều ghi chế độ chạy vào sổ', () => {
  // Hai đường: thành công và hỏng. Thiếu một đường thì báo cáo hiệu chỉnh
  // đếm hụt đúng nhóm đáng lo nhất.
  const than = thanRoute('/product-scene')
  const soLogCreate = h.demGoi(than, 'UsageLog.create')
  // Đếm ĐÚNG dạng ghi sổ. Đếm mọi `runMode:` là đếm lây cả điều kiện lọc
  // `runMode: { $ne: 'test_now' }` của phép đếm hạn mức — con số phồng lên
  // và test xanh nhầm. Đã mắc đúng lỗi đó khi thêm nút Thử ngay.
  const soGhiRunMode = (than.match(/runMode: nac\.runMode/g) || []).length
  assert.equal(soGhiRunMode, soLogCreate,
    `${soLogCreate} chỗ ghi sổ nhưng chỉ ${soGhiRunMode} chỗ ghi chế độ chạy`)
})

test('cửa trợ lý ghi phán quyết của bước kiểm bao bì', () => {
  assert.match(thanRoute('/assist'), /verdict:/)
})

test('runMode không bao giờ lấy từ thân yêu cầu', () => {
  // Client tự khai "tôi đang chạy production" thì báo cáo hiệu chỉnh thành
  // vô nghĩa. Không được có chỗ nào đọc runMode/run_mode từ body.
  assert.doesNotMatch(NGUON, /body\.run_?[Mm]ode/,
    'có chỗ đọc chế độ chạy từ thân yêu cầu')
})
