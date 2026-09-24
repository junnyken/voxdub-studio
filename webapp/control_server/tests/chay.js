#!/usr/bin/env node
'use strict'

/**
 * Chạy bộ test Node với ĐÚNG MỘT `mongod` dùng chung (21-08).
 *
 * Trước đây `npm test` là `node --test tests/*.test.js`: mỗi tệp tự dựng một
 * `MongoMemoryServer`, 12 tệp chạy song song = 12 `mongod`. Trên máy đang bận
 * thì đỏ hàng loạt — đo thật: hai lượt chạy song song ra **55 đỏ và 81 đỏ**,
 * cùng mã nguồn mà lượt chạy đơn độc 0 đỏ. Kết quả phụ thuộc máy rảnh hay bận
 * thì không dùng làm bằng chứng được.
 *
 * Tệp này dựng một `mongod`, truyền địa chỉ qua `TEST_MONGO_URI`, và
 * `tests/helpers/db.js` cấp cho mỗi tiến trình một database riêng — cách ly
 * giữ nguyên, bộ nhớ giảm 12 lần.
 *
 * Dùng:
 *     npm test                          # cả bộ
 *     npm test -- tests/hold.test.js    # vài tệp
 */
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { MongoMemoryServer } = require('mongodb-memory-server')

const GOC = path.join(__dirname, '..')

function cacTep() {
  const chon = process.argv.slice(2)
  if (chon.length > 0) return chon
  return fs
    .readdirSync(__dirname)
    .filter((ten) => ten.endsWith('.test.js'))
    .sort()
    .map((ten) => path.join('tests', ten))
}

async function main() {
  const tep = cacTep()
  if (tep.length === 0) {
    console.error('Không thấy tệp .test.js nào trong tests/')
    process.exit(1)
  }

  const mongod = await MongoMemoryServer.create()
  let ma = 1
  try {
    const con = spawn(process.execPath, ['--test', ...tep], {
      cwd: GOC,
      stdio: 'inherit',
      env: { ...process.env, TEST_MONGO_URI: mongod.getUri() },
    })
    // Ctrl-C phải xuống tới tiến trình con, rồi `finally` mới dọn `mongod` —
    // bỏ qua bước này là để lại một mongod mồ côi mỗi lần bấm huỷ.
    const chuyenTiep = (tin) => con.kill(tin)
    process.on('SIGINT', chuyenTiep)
    process.on('SIGTERM', chuyenTiep)
    ma = await new Promise((xong) => {
      con.on('exit', (code, tin) => xong(tin ? 1 : code ?? 1))
      con.on('error', (loi) => {
        console.error(loi)
        xong(1)
      })
    })
  } finally {
    await mongod.stop()
  }
  process.exit(ma)
}

main().catch((loi) => {
  console.error(loi)
  process.exit(1)
})
