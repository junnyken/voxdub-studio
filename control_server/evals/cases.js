'use strict'

/**
 * Bộ mẫu đo chất lượng cổng trợ lý (mini-spec V89, giai đoạn 2).
 *
 * Mỗi mẫu gồm đầu vào THẬT và các phép kiểm chạy được bằng máy. Cố ý KHÔNG
 * dùng "đáp án mẫu" do người viết: chấm theo đáp án mẫu đòi người đọc từng
 * lượt, nên chạy vài lần là bỏ. Thay vào đó kiểm những TÍNH CHẤT mà kết quả
 * sai chắc chắn vi phạm:
 *
 *   - câu rút gọn phải NGẮN HƠN câu gốc và giữ nguyên con số
 *   - từ khoá tóm tắt phải CÓ trong lời thoại (bắt bịa)
 *   - lời giải thích lỗi không được chứa từ kỹ thuật
 *   - mô tả nhạc phải nói về âm nhạc, không phải về hình ảnh
 *
 * Đây là thứ chặn "hỏng âm thầm": mô hình vẫn trả lời, chỉ là trả lời kém đi.
 */

/** Có ít nhất một trong các từ này (không phân biệt hoa thường). */
function coMot(tu) {
  return (r) => tu.some((t) => r.value.toLowerCase().includes(t))
}

/** Không được chứa bất kỳ từ nào trong danh sách. */
function khongCo(tu) {
  return (r) => !tu.some((t) => `${r.value} ${r.reason}`.toLowerCase().includes(t))
}

function ngan(max) {
  return (r) => r.value.split(/\s+/).filter(Boolean).length <= max
}

const LOI_THOAI_NAU_AN = [
  'Hôm nay mình sẽ hướng dẫn các bạn nấu món phở bò truyền thống.',
  'Nguyên liệu gồm hai ký xương ống, một củ gừng nướng, quế và hoa hồi.',
  'Xương phải chần qua nước sôi rồi rửa sạch thì nước dùng mới trong.',
  'Ninh xương trong sáu tiếng, hớt bọt liên tục cho tới khi nước ngọt hẳn.',
  'Bánh phở trụng nhanh thôi, trụng lâu là bở mất ngon.',
].join(' ')

const LOI_THOAI_GAME = [
  'Trận này mình dùng tướng Yasuo đi đường giữa, ngọc bổ trợ chí mạng.',
  'Yasuo cần cộng dồn chí mạng nên hai món đầu phải là kiếm vô cực.',
  'Đối phương chọn Zed, mà Zed cấu máu rất mạnh ở cấp ba.',
  'Nên mình giữ khoảng cách, đợi hết chiêu của Zed rồi mới vào.',
].join(' ')

const CASES = [
  {
    task: 'music_suggest',
    ten: 'video nấu ăn — nhạc phải mộc, không dồn dập',
    input: { transcript: LOI_THOAI_NAU_AN, videoTitle: 'Nấu phở bò tại nhà' },
    kiem: [
      ['mô tả về âm nhạc chứ không về hình ảnh',
        coMot(['nhạc', 'guitar', 'piano', 'tiết tấu', 'giai điệu', 'acoustic',
          'mộc', 'trống', 'sáo', 'đàn'])],
      ['không nhắc tên bài hát hay ca sĩ có thật',
        khongCo(['sơn tùng', 'taylor swift', 'bài hát "', 'ca khúc "'])],
      ['đủ ngắn để đưa thẳng cho máy sinh nhạc', ngan(25)],
    ],
  },
  {
    task: 'music_suggest',
    ten: 'video game — nhạc phải có năng lượng',
    input: { transcript: LOI_THOAI_GAME, videoTitle: 'Hướng dẫn đi đường giữa' },
    kiem: [
      ['mô tả về âm nhạc', coMot(['nhạc', 'tiết tấu', 'điện tử', 'trống',
        'giai điệu', 'nhịp'])],
      ['không mô tả hình ảnh', khongCo(['màu sắc', 'khung hình', 'cảnh quay'])],
    ],
  },
  {
    task: 'explain_error',
    ten: 'thiếu FFmpeg — đúng lỗi người dùng gặp 19-08',
    input: {
      message: '[WinError 2] The system cannot find the file specified',
      step: 'chép lời',
    },
    kiem: [
      ['không ném từ kỹ thuật vào mặt người dùng',
        khongCo(['winerror', 'traceback', 'exception', 'module', 'subprocess',
          'stderr', 'path=', 'venv'])],
      ['không bảo người dùng đi báo lỗi trên GitHub',
        khongCo(['github', 'issue', 'báo lỗi cho nhà phát triển'])],
      ['nói được việc cần làm', (r) => r.value.length >= 15],
    ],
  },
  {
    task: 'explain_error',
    ten: 'lỗi mơ hồ — phải nói thẳng là chưa rõ, không bịa cách sửa',
    input: { message: 'Error: EPIPE broken pipe at unknown', step: 'xuất video' },
    kiem: [
      ['không bịa ra một cách sửa nghe có vẻ hợp lý',
        khongCo(['cài lại windows', 'định dạng ổ cứng', 'mua thêm'])],
      ['không dùng từ kỹ thuật', khongCo(['epipe', 'broken pipe', 'stack'])],
    ],
  },
  {
    task: 'tighten_line',
    ten: 'câu dài 1,6 lần chỗ trống',
    input: {
      line: 'Và như các bạn có thể thấy ở đây thì cái phần này nó thực sự là '
        + 'rất quan trọng đối với toàn bộ quá trình mà chúng ta đang làm.',
      needSeconds: 8, roomSeconds: 5, trimPercent: 38,
    },
    kiem: [
      ['phải ngắn hơn câu gốc rõ rệt',
        (r, c) => r.value.length <= c.input.line.length * 0.75],
      ['vẫn là tiếng Việt đọc được, không viết tắt',
        khongCo(['k ', 'ko ', 'vs ', 'đc '])],
    ],
  },
  {
    task: 'tighten_line',
    ten: 'câu có số và tên riêng — không được làm mất',
    input: {
      line: 'Ninh xương ống trong sáu tiếng với hai ký xương và một củ gừng '
        + 'nướng thì nước dùng mới đủ ngọt và trong.',
      needSeconds: 7, roomSeconds: 5, trimPercent: 28,
    },
    kiem: [
      ['giữ nguyên con số', (r) => /sáu|6/.test(r.value) && /hai|2/.test(r.value)],
      ['ngắn hơn câu gốc',
        (r, c) => r.value.length < c.input.line.length],
    ],
  },
  {
    task: 'video_summary',
    ten: 'từ khoá phải lấy TỪ lời thoại, không tự nghĩ',
    input: { transcript: LOI_THOAI_NAU_AN, videoTitle: 'Nấu phở bò tại nhà' },
    kiem: [
      ['mọi từ khoá đều có trong lời thoại',
        (r, c) => r.reason.toLowerCase().includes('tóm tắt')
          || c.input.transcript.toLowerCase().includes(r.value.toLowerCase())],
    ],
  },
  {
    task: 'character_name',
    ten: 'tên phải ngắn để vừa bảng hồ sơ',
    input: {
      lines: 'Kính thưa quý vị và các bạn. Sau đây là bản tin tối nay. '
        + 'Chúng tôi sẽ trở lại sau ít phút quảng cáo.',
      lineCount: 3,
    },
    kiem: [
      ['tối đa 3 chữ', ngan(3)],
      ['không đoán giới tính khi lời thoại không cho biết',
        khongCo(['cô gái', 'chàng trai', 'bà ', 'ông '])],
    ],
  },
  {
    task: 'series_glossary',
    ten: 'thuật ngữ phải có thật trong lời thoại',
    input: { transcript: LOI_THOAI_GAME, seriesName: 'Hướng dẫn Yasuo' },
    kiem: [
      ['mục đầu là cách xưng hô',
        (r, _c, i) => i > 0 || /–|-|với|xưng/.test(r.value)],
      ['thuật ngữ lấy từ lời thoại',
        (r, c, i) => i === 0
          || c.input.transcript.toLowerCase().includes(
            r.value.split('=')[0].trim().toLowerCase())],
    ],
  },
]

module.exports = { CASES }
