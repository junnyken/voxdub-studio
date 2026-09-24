'use strict'

/**
 * Mini-spec V10 (docs/PLAN.md) — retention cohort theo tuần, dùng lại
 * Device.firstSeenAt/lastSeenAt đã có sẵn, không thêm thu thập dữ liệu mới.
 *
 * Chạy:  node --test tests/retention.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { computeWeeklyRetention, startOfWeek, weekLabel } = require('../src/services/retention.service')

const DAY = 24 * 3600 * 1000
const WEEK = 7 * DAY

test('startOfWeek: luôn ra đúng Thứ Hai', () => {
  // 2026-08-11 là Thứ Ba.
  const monday = startOfWeek(new Date('2026-08-11T15:00:00Z'))
  assert.equal(weekLabel(monday), '2026-08-10')
  assert.equal(monday.getUTCDay(), 1)
})

test('startOfWeek: đúng ngay Thứ Hai thì giữ nguyên', () => {
  const monday = startOfWeek(new Date('2026-08-10T09:00:00Z'))
  assert.equal(weekLabel(monday), '2026-08-10')
})

test('cohort đăng ký tuần này (offset 0) luôn 100% — chính là lúc đăng ký', () => {
  const now = new Date('2026-08-11T00:00:00Z')
  const devices = [
    { firstSeenAt: '2026-08-10T08:00:00Z', lastSeenAt: '2026-08-10T08:00:00Z' },
    { firstSeenAt: '2026-08-11T08:00:00Z', lastSeenAt: '2026-08-11T08:00:00Z' },
  ]
  const result = computeWeeklyRetention(devices, 4, now)
  assert.equal(result.length, 1)
  assert.equal(result[0].cohortSize, 2)
  assert.equal(result[0].retention[0].pct, 100)
})

test('thiết bị không quay lại thì retention tuần sau = 0%', () => {
  const now = new Date('2026-08-24T00:00:00Z')   // 2 tuần sau cohort
  const devices = [
    // Đăng ký tuần 2026-08-10, KHÔNG quay lại (lastSeenAt = ngay lúc đăng ký).
    { firstSeenAt: '2026-08-10T08:00:00Z', lastSeenAt: '2026-08-10T08:00:00Z' },
  ]
  const result = computeWeeklyRetention(devices, 4, now)
  const cohort = result.find((c) => c.cohortWeek === '2026-08-10')
  assert.ok(cohort)
  assert.equal(cohort.retention[0].pct, 100, 'tuần 0 luôn 100%')
  assert.equal(cohort.retention[1].pct, 0, 'không quay lại thì tuần 1 phải 0%')
})

test('thiết bị vẫn hoạt động tới hiện tại thì retention mọi tuần đều 100%', () => {
  const now = new Date('2026-08-31T00:00:00Z')   // 3 tuần sau cohort
  const devices = [
    // lastSeenAt = đúng "now" — thiết bị hoạt động tới tận lúc đo.
    { firstSeenAt: '2026-08-10T08:00:00Z', lastSeenAt: '2026-08-31T00:00:00Z' },
  ]
  const result = computeWeeklyRetention(devices, 4, now)
  const cohort = result.find((c) => c.cohortWeek === '2026-08-10')
  for (const r of cohort.retention) {
    assert.equal(r.pct, 100, `offset ${r.offsetWeeks} phải 100%`)
  }
})

test('nhiều cohort khác tuần được tách đúng, không trộn lẫn', () => {
  const now = new Date('2026-08-24T00:00:00Z')
  const devices = [
    { firstSeenAt: '2026-08-03T08:00:00Z', lastSeenAt: '2026-08-03T08:00:00Z' },
    { firstSeenAt: '2026-08-10T08:00:00Z', lastSeenAt: '2026-08-10T08:00:00Z' },
    { firstSeenAt: '2026-08-10T09:00:00Z', lastSeenAt: '2026-08-17T09:00:00Z' },
  ]
  const result = computeWeeklyRetention(devices, 4, now)
  const w1 = result.find((c) => c.cohortWeek === '2026-08-03')
  const w2 = result.find((c) => c.cohortWeek === '2026-08-10')
  assert.equal(w1.cohortSize, 1)
  assert.equal(w2.cohortSize, 2)
  assert.equal(w2.retention[1].pct, 50, '1 trong 2 thiết bị còn hoạt động tuần kế')
})

test('thiết bị thiếu firstSeenAt bị bỏ qua an toàn, không crash', () => {
  const now = new Date('2026-08-11T00:00:00Z')
  const devices = [{ lastSeenAt: '2026-08-10T08:00:00Z' }]
  assert.doesNotThrow(() => computeWeeklyRetention(devices, 4, now))
  assert.deepEqual(computeWeeklyRetention(devices, 4, now), [])
})

test('không có thiết bị nào thì trả mảng rỗng', () => {
  assert.deepEqual(computeWeeklyRetention([], 4, new Date('2026-08-11T00:00:00Z')), [])
})

test('chỉ trả về đúng số tuần yêu cầu (weeks), lấy cohort gần nhất', () => {
  const now = new Date('2026-09-01T00:00:00Z')
  const devices = []
  for (let i = 0; i < 10; i += 1) {
    devices.push({
      firstSeenAt: new Date(Date.parse('2026-07-06T08:00:00Z') + i * WEEK).toISOString(),
      lastSeenAt: new Date(Date.parse('2026-07-06T08:00:00Z') + i * WEEK).toISOString(),
    })
  }
  const result = computeWeeklyRetention(devices, 3, now)
  assert.equal(result.length, 3)
})
