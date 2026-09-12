'use strict'

/**
 * `src/utils/dub-langs.js` là bản sao thủ công của `autodub/languages.py`.
 * Bản sao thủ công thì sớm muộn cũng lệch, nên test này đọc THẲNG file
 * Python và so từng mã — thêm ngôn ngữ một bên mà quên bên kia là fail
 * ngay, không phải chờ tới lúc người dùng gặp lỗi mơ hồ ở cuối pipeline.
 *
 * Chạy:  node --test tests/dub-langs.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const { SOURCE_LANGS, TARGET_LANGS, isValidSourceLang, isValidTargetLang } =
  require('../src/utils/dub-langs')

const PY_LANGS = path.join(__dirname, '..', '..', 'autodub', 'languages.py')

/** Mã trong SOURCE_LANG_MAP của Python (khoá, không phải giá trị). */
function pySourceLangs(src) {
  const block = src.slice(src.indexOf('SOURCE_LANG_MAP'))
  const body = block.slice(0, block.indexOf('}'))
  return [...body.matchAll(/^\s*"([\w-]+)":/gm)].map((m) => m[1])
}

/** Khoá của TARGETS: literal `"xx": TargetLang(` + bảng mở rộng _V17_TARGETS. */
function pyTargetLangs(src) {
  const targetsBlock = src.slice(src.indexOf('TARGETS: dict'))
  const direct = [...targetsBlock.matchAll(/^\s{4}"(\w+)": TargetLang\(/gm)].map((m) => m[1])
  const v17Block = src.slice(src.indexOf('_V17_TARGETS = ['))
  const v17 = [...v17Block.slice(0, v17Block.indexOf(']')).matchAll(/\(\s*"(\w+)",/g)]
    .map((m) => m[1])
  return [...new Set([...direct, ...v17])]
}

test('dub-langs khớp autodub/languages.py', (t) => {
  // Nhánh deploy sinh tự động chỉ chứa control_server/ + website/ nên không
  // có file Python — bỏ qua thay vì fail giả ở môi trường đó.
  if (!fs.existsSync(PY_LANGS)) {
    t.skip('không thấy autodub/languages.py (nhánh deploy rút gọn)')
    return
  }
  const src = fs.readFileSync(PY_LANGS, 'utf8')

  const pySources = pySourceLangs(src)
  assert.ok(pySources.length > 0, 'không đọc được SOURCE_LANG_MAP từ Python')
  assert.deepStrictEqual([...SOURCE_LANGS].sort(), [...pySources].sort(),
    'SOURCE_LANGS lệch với SOURCE_LANG_MAP trong autodub/languages.py')

  const pyTargets = pyTargetLangs(src)
  assert.ok(pyTargets.length > 0, 'không đọc được TARGETS từ Python')
  assert.deepStrictEqual([...TARGET_LANGS].sort(), [...pyTargets].sort(),
    'TARGET_LANGS lệch với TARGETS trong autodub/languages.py')
})

test('nhận cả dạng ngắn lẫn BCP-47 cho sourceLang', () => {
  assert.ok(isValidSourceLang('vi'))
  assert.ok(isValidSourceLang('vi-VN'))
  assert.ok(isValidSourceLang(' en-US '), 'phải bỏ khoảng trắng thừa')
})

test('targetLang chỉ nhận khoá ngắn, không nhận BCP-47', () => {
  assert.ok(isValidTargetLang('vi'))
  // Đây chính là cái bẫy đã gây ra lỗi thật: "vi-VN" trông rất hợp lý ở
  // tham số bên cạnh nhưng KHÔNG phải khoá TARGETS.
  assert.ok(!isValidTargetLang('vi-VN'))
})

test('từ chối mã rác và giá trị rỗng', () => {
  for (const bad of ['', '   ', 'xx', 'klingon', null, undefined]) {
    assert.ok(!isValidSourceLang(bad), `sourceLang phải từ chối: ${JSON.stringify(bad)}`)
    assert.ok(!isValidTargetLang(bad), `targetLang phải từ chối: ${JSON.stringify(bad)}`)
  }
})
