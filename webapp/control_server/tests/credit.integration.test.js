'use strict'

/**
 * Integration test: ví Vox chạm MongoDB thật (in-memory) — không mock chính
 * cái đang kiểm tra (credit.service). Bổ sung cho hold.test.js (chỉ test
 * phần thuần) theo mini-spec V1 (docs/PLAN.md).
 *
 * Chạy:  node --test tests/credit.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const Device = require('../src/models/Device')
const credit = require('../src/services/credit.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

async function makeDevice(fingerprint, balance = 0) {
  return Device.create({ fingerprint, balance, status: 'active' })
}

test('deduct: hai request đồng thời rút cùng ví — đúng một cái thắng, ví không bao giờ âm', async () => {
  const fp = 'a'.repeat(64)
  await makeDevice(fp, 100)

  const results = await Promise.allSettled([
    credit.deduct(fp, 80, { idempotencyKey: 'race-1' }),
    credit.deduct(fp, 80, { idempotencyKey: 'race-2' }),
  ])

  const fulfilled = results.filter((r) => r.status === 'fulfilled')
  const rejected = results.filter((r) => r.status === 'rejected')
  assert.equal(fulfilled.length, 1, 'chỉ đúng một request được trừ thành công')
  assert.equal(rejected.length, 1, 'request còn lại phải bị từ chối (không đủ credit)')
  assert.ok(rejected[0].reason instanceof credit.InsufficientCreditError)

  const balance = await credit.getBalance(fp)
  assert.equal(balance, 20, 'ví phải còn đúng 20 (100 - 80), không âm, không trừ hai lần')
})

test('deduct: cùng idempotencyKey gọi lại không trừ thêm lần hai', async () => {
  const fp = 'b'.repeat(64)
  await makeDevice(fp, 100)

  const first = await credit.deduct(fp, 30, { idempotencyKey: 'same-key' })
  const second = await credit.deduct(fp, 30, { idempotencyKey: 'same-key' })

  assert.equal(first.replayed, false)
  assert.equal(second.replayed, true)
  assert.equal(await credit.getBalance(fp), 70, 'chỉ trừ đúng một lần dù gọi hai lần')
})

test('grant: cùng idempotencyKey gọi lại không cộng thêm lần hai', async () => {
  const fp = 'c'.repeat(64)
  await makeDevice(fp, 0)

  await credit.grant(fp, 50, { idempotencyKey: 'grant-1' })
  await credit.grant(fp, 50, { idempotencyKey: 'grant-1' })

  assert.equal(await credit.getBalance(fp), 50, 'grant lặp lại với cùng key không cộng thêm')
})

test('deduct: rút quá số dư bị từ chối, ví không đổi', async () => {
  const fp = 'd'.repeat(64)
  await makeDevice(fp, 10)

  await assert.rejects(
    () => credit.deduct(fp, 999, { idempotencyKey: 'too-much' }),
    credit.InsufficientCreditError,
  )
  assert.equal(await credit.getBalance(fp), 10, 'ví phải giữ nguyên khi bị từ chối')
})

test('reconcile: ví khớp sổ cái sau nhiều giao dịch xen kẽ', async () => {
  const fp = 'e'.repeat(64)
  await makeDevice(fp, 0)

  await credit.grant(fp, 200, { idempotencyKey: 'g1' })
  await credit.deduct(fp, 50, { idempotencyKey: 'd1' })
  await credit.deduct(fp, 30, { idempotencyKey: 'd2' })
  await credit.grant(fp, 10, { idempotencyKey: 'g2' })

  assert.equal(await credit.getBalance(fp), 130)
  const { mismatches } = await credit.reconcile()
  assert.deepEqual(mismatches, [], 'không được lệch giữa Device.balance và tổng CreditLedger.delta')
})

test('deduct: idempotencyKey là bắt buộc — thiếu thì ném lỗi ngay, không chạm DB', async () => {
  const fp = 'f'.repeat(64)
  await makeDevice(fp, 100)
  await assert.rejects(() => credit.deduct(fp, 10, {}), /idempotencyKey/)
  assert.equal(await credit.getBalance(fp), 100)
})
