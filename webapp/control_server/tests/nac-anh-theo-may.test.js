'use strict'

/**
 * Nấc tính năng ảnh trả lời theo TỪNG MÁY (mini-spec C18).
 *
 * Cửa ghép video trước đây chỉ mở ở nấc `production`. Đúng tinh thần — đừng
 * đem ảnh chưa ai soi tay đi làm nội dung bán hàng — nhưng chặn nhầm đúng
 * người đang chạy đợt hiệu chỉnh: chính chủ shop, trên chính máy đã được
 * duyệt, muốn xem thử cả chuỗi trước khi bỏ 660 Vox.
 *
 * Nay mở kèm cảnh báo. Hai chỗ dễ làm hỏng:
 *
 * - Mở cho máy KHÔNG nằm trong danh sách hiệu chỉnh (thành mở cho tất cả).
 * - Mở mà quên câu cảnh báo (người dùng cầm video đi đăng).
 */
const test = require('node:test')
const assert = require('node:assert')

const imageStage = require('../src/services/image-stage.service')

const MAY_A = 'a'.repeat(64)
const MAY_B = 'b'.repeat(64)

/** Đúng phép tính route dùng để trả lời. */
function traLoi({ stage, devices, fingerprint }) {
  const nac = imageStage.quyetDinh({ stage, devices, fingerprint })
  const thu = nac.runMode === 'calibration'
  return {
    runMode: nac.runMode || '',
    videoDuoc: Boolean(nac.runMode),
    canhBao: thu ? 'bản dựng thử, đừng đăng bán' : '',
  }
}

test('nấc tắt: không máy nào dựng được video', () => {
  const ra = traLoi({ stage: 'off', devices: MAY_A, fingerprint: MAY_A })
  assert.strictEqual(ra.videoDuoc, false)
})

test('nấc hiệu chỉnh: máy TRONG danh sách dựng được, kèm cảnh báo', () => {
  const ra = traLoi({ stage: 'calibration', devices: MAY_A, fingerprint: MAY_A })
  assert.strictEqual(ra.videoDuoc, true)
  assert.strictEqual(ra.runMode, 'calibration')
  assert.match(ra.canhBao, /đừng đăng bán/)
})

test('nấc hiệu chỉnh: máy NGOÀI danh sách vẫn bị chặn', () => {
  const ra = traLoi({ stage: 'calibration', devices: MAY_A, fingerprint: MAY_B })
  assert.strictEqual(ra.videoDuoc, false,
    'mở cho máy ngoài danh sách là mở cho tất cả')
})

test('nấc chạy thật: mở cho mọi máy, KHÔNG cảnh báo', () => {
  const ra = traLoi({ stage: 'production', devices: '', fingerprint: MAY_B })
  assert.strictEqual(ra.videoDuoc, true)
  assert.strictEqual(ra.canhBao, '',
    'cảnh báo ở nấc chạy thật là dạy người dùng bỏ qua cảnh báo')
})

test('route hỏi nấc theo vân tay của MÁY ĐANG GỌI', () => {
  const { thanHam } = require('./helpers/doc-ma')
  const than = thanHam('src/routes/ai.js', '/scene-stage')
  assert.match(than, /device\.fingerprint/,
    'không lấy vân tay máy gọi thì câu trả lời đúng cho người này, sai cho '
    + 'người kia')
})
