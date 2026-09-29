'use strict'

/**
 * Integration test: kích hoạt mã Vox chạm MongoDB thật (in-memory) — quy tắc
 * bất di bất dịch "một key dùng đúng một lần trên đúng một thiết bị" theo
 * mini-spec V1 (docs/PLAN.md).
 *
 * Chạy:  node --test tests/activation.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const Device = require('../src/models/Device')
const activation = require('../src/services/activation.service')
const credit = require('../src/services/credit.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

async function makeDevice(fingerprint) {
  return Device.create({ fingerprint, balance: 0, status: 'active' })
}

test('kích hoạt key hợp lệ cộng đúng số Vox vào ví', async () => {
  const fp = 'a'.repeat(64)
  await makeDevice(fp)
  const key = await activation.issueKey({ vox: 1000 })

  const result = await activation.activate(fp, key.code)
  assert.equal(result.vox, 1000)
  assert.equal(result.balanceAfter, 1000)
  assert.equal(await credit.getBalance(fp), 1000)
})

test('key đã dùng không kích hoạt được trên thiết bị khác', async () => {
  const fpA = 'b'.repeat(64)
  const fpB = 'c'.repeat(64)
  await makeDevice(fpA)
  await makeDevice(fpB)
  const key = await activation.issueKey({ vox: 500 })

  await activation.activate(fpA, key.code)
  await assert.rejects(
    () => activation.activate(fpB, key.code),
    (err) => err.code === 'KEY_ALREADY_USED',
  )
  assert.equal(await credit.getBalance(fpB), 0, 'thiết bị bị từ chối không được cộng Vox')
})

test('kích hoạt lại cùng key trên CHÍNH thiết bị đó là idempotent, không cộng thêm', async () => {
  const fp = 'd'.repeat(64)
  await makeDevice(fp)
  const key = await activation.issueKey({ vox: 300 })

  const first = await activation.activate(fp, key.code)
  const second = await activation.activate(fp, key.code)

  assert.equal(first.alreadyActivated, false)
  assert.equal(second.alreadyActivated, true)
  assert.equal(await credit.getBalance(fp), 300, 'không được cộng hai lần')
})

test('key không tồn tại bị từ chối rõ ràng', async () => {
  const fp = 'e'.repeat(64)
  await makeDevice(fp)
  await assert.rejects(
    () => activation.activate(fp, 'VOX-ZZZZ-ZZZZ-ZZZZ'),
    (err) => err.code === 'KEY_NOT_FOUND',
  )
})

test('hai request kích hoạt CÙNG key đồng thời trên hai máy khác nhau — đúng một máy thắng', async () => {
  const fpA = 'f'.repeat(64)
  const fpB = '1'.repeat(64)
  await makeDevice(fpA)
  await makeDevice(fpB)
  const key = await activation.issueKey({ vox: 700 })

  const results = await Promise.allSettled([
    activation.activate(fpA, key.code),
    activation.activate(fpB, key.code),
  ])
  const fulfilled = results.filter((r) => r.status === 'fulfilled')
  assert.equal(fulfilled.length, 1, 'đúng một máy kích hoạt thành công — key không thể dùng cho cả hai')

  const totalGranted = (await credit.getBalance(fpA)) + (await credit.getBalance(fpB))
  assert.equal(totalGranted, 700, 'tổng Vox cấp ra đúng bằng một lần kích hoạt, không nhân đôi')
})
