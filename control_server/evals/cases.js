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
    task: 'scene_continuity',
    ten: 'kiểm liên tục giữa các cảnh — cần ẢNH THẬT nên không chấm khô được',
    input: { note: 'video 4 cảnh cho một hộp trà' },
    // Cùng lý do với `packaging_check`: tác vụ này nhìn ảnh, không đọc chữ.
    canAnh: true,
    kiem: [
      ['chỉ trả MUOT hoặc LECH',
        (r) => ['MUOT', 'LECH'].includes(r.value.trim().toUpperCase())],
      ['nói rõ cảnh nào lạc', (r) => r.reason.length >= 8],
    ],
  },
  {
    task: 'scene_script',
    ten: 'gợi ý kịch bản — mỗi cảnh một câu dẫn ngắn',
    input: {
      product: 'trà gừng mật ong, túi zip 1kg',
      scenes: ['bàn gỗ mộc', 'giỏ quà', 'trên tay'],
    },
    kiem: [
      ['câu dẫn đủ ngắn để hiện trên màn hình',
        (r) => r.value.trim().split(/\s+/).length <= 12],
      ['có gợi ý nhịp cho cảnh đó', (r) => r.reason.length >= 5],
      // Câu chữ bán hàng sai luật là rủi ro của NGƯỜI BÁN, không phải của mô
      // hình — nên chặn ngay ở mẫu đo, đừng đợi ai đó phát hiện trên TikTok.
      ['không hứa công dụng chữa bệnh',
        (r) => !/chữa|trị bệnh|khỏi bệnh|thuốc/i.test(r.value)],
      ['không dùng từ tuyệt đối',
        (r) => !/tốt nhất|số một|số 1|duy nhất|hàng đầu/i.test(r.value)],
    ],
  },
  {
    task: 'packaging_check',
    ten: 'cổng kiểm tuân thủ — cần ẢNH THẬT nên không chấm khô được',
    input: { note: 'túi zip 1kg, nhãn giấy dán mặt trước' },
    // Tác vụ này so HAI ẢNH, không so chữ. Chạy thật cần ảnh sản phẩm thật,
    // nên phần chấm tự động chỉ kiểm được khuôn câu hỏi. Đánh dấu rõ để bộ
    // đo BÁO BỎ QUA thay vì âm thầm cho điểm 100% — một mẫu luôn đạt vì
    // không kiểm gì cả còn tệ hơn không có mẫu (bài học V93).
    canAnh: true,
    kiem: [
      ['chỉ trả SAFE hoặc CONCEPT',
        (r) => ['SAFE', 'CONCEPT'].includes(r.value.trim().toUpperCase())],
      ['nói rõ đã khác chỗ nào', (r) => r.reason.length >= 8],
    ],
  },
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
  {
    // Mini-spec H2 — khuôn output KHÁC hẳn (beats[], không phải
    // results[{value,reason}]) nên `kiem` kiểm thẳng trường snake_case của
    // MÔ HÌNH trả về (đúng khuôn `flowBlueprintOutputSchema()`), không phải
    // khuôn camelCase đã chuẩn hoá của `parseFlowBlueprintResult()`.
    task: 'viral_flow_blueprint',
    ten: 'hook tiếng Anh phải ra beat mô tả, không chép nguyên câu nguồn',
    input: {
      languageSourceDetected: 'en',
      samplingPolicyUsed: '0-5s=0.2s,middle=0.5s,last-5s=0.2s',
      transcript: [
        { start_s: 0, end_s: 2.5,
          text: 'Stop wasting money on skincare that does nothing for you.' },
        { start_s: 2.5, end_s: 6,
          text: 'Here is the one ingredient dermatologists never tell you about.' },
      ],
      ocrEvidence: [
        { start_s: 0.2, end_s: 0.6, status: 'ok', text: 'STOP SCROLLING' },
      ],
    },
    kiem: [
      ['beat_type nằm trong vocabulary đóng',
        (r) => require('../src/prompts/assist').flowBlueprintOutputSchema()
          .properties.beats.items.properties.beat_type.enum.includes(r.beat_type)],
      ['start_s < end_s',
        (r) => Number(r.start_s) < Number(r.end_s)],
      ['không chép nguyên văn transcript/OCR nguồn vào các trường mô tả',
        (r, c) => {
          const assist = require('../src/prompts/assist')
          const nguon = [...c.input.transcript.map((d) => d.text),
            ...c.input.ocrEvidence.map((o) => o.text)]
          const cacTruong = ['narrative_function_vi', 'pacing_note_vi',
            'overlay_pattern_abstract_vi', 'spoken_pattern_abstract_vi']
          return !cacTruong.some((t) => assist.coSaoChepNguyenVan(String(r[t] || ''), nguon))
        }],
    ],
  },
  {
    // Mini-spec H2b — mẫu đo DUY NHẤT có ảnh. Cả tác vụ sinh ra chỉ vì một
    // chuyện: OCR trên máy đọc tiếng Việt MẤT DẤU. Nên phép chấm ở đây phải
    // ĐỎ khi chữ mất dấu, chứ không chỉ kiểm "có đọc ra chữ gì đó".
    task: 'doc_chu_khung_hinh',
    ten: 'đọc caption tiếng Việt phải RA ĐÚNG DẤU, không phải bản mất dấu',
    anh: ['fixtures/chu_tieng_viet.png'],
    input: { soAnh: 1 },
    kiem: [
      ['đúng số thứ tự ảnh', (r) => Number(r.anh) === 1],
      ['đọc ra đúng nguyên văn CÓ DẤU',
        (r) => (r.dong || []).some(
          (d) => String(d).includes('Đăng ký kênh để không bỏ lỡ video mới'))],
      ['KHÔNG trả về bản mất dấu kiểu OCR cũ',
        (r) => !(r.dong || []).some((d) => /Dang ky kenh/i.test(String(d)))],
      ['không dịch sang ngôn ngữ khác',
        (r) => !(r.dong || []).some((d) => /subscribe|channel/i.test(String(d)))],
    ],
  },
  {
    // Mini-spec H3 — khuôn output riêng (`doan[]`), `kiem` nhận thẳng trường
    // snake_case của MÔ HÌNH, không phải khuôn camelCase đã chuẩn hoá.
    //
    // Mẫu này cố tình đặt ràng buộc "tốt nhất" để đo LỚP PHÒNG ĐẦU (model tự
    // tránh trong lúc sinh). Lớp CHẶN thật nằm ở `kiem-kich-ban.service.js`
    // chạy sau — mẫu đo không thay thế nó được, vì model "hứa" tránh không có
    // nghĩa nó thực sự tránh.
    task: 'brand_script_rewrite',
    ten: 'viết đúng số đoạn, đúng brand, không đụng cụm bị cấm',
    input: {
      brand: {
        tenBrand: 'Bếp Nhà Vui',
        moTaSanPham: 'Nồi chiên không dầu dung tích 5 lít cho gia đình 3-4 người',
        doiTuongKhach: 'Mẹ bỉm sữa 25-35 tuổi ở thành phố, ít thời gian nấu ăn',
        toneGiong: 'Gần gũi, như bạn bè mách nhau, không hô hào',
        usp: 'Làm nóng nhanh trong 3 phút, lòng nồi chống dính rửa được bằng máy',
        rangBuocKhongDuocNoi: ['tốt nhất', 'số một', 'chữa bệnh'],
      },
      beats: [
        { beatType: 'hook', narrativeFunctionVi: 'Nêu một nỗi bực quen thuộc của người xem', pacingNoteVi: 'Rất nhanh, câu cực ngắn' },
        { beatType: 'proof', narrativeFunctionVi: 'Đưa bằng chứng cụ thể rằng vấn đề giải quyết được', pacingNoteVi: 'Chậm lại, cho người xem kịp nhìn' },
        { beatType: 'cta', narrativeFunctionVi: 'Mời hành động, nhẹ nhàng không thúc ép', pacingNoteVi: 'Ngắn, dứt khoát' },
      ],
    },
    kiem: [
      ['đủ ba trường cho mỗi đoạn',
        (r) => Boolean(String(r.loi_doc || '').trim())
          && Boolean(String(r.caption || '').trim())
          && Boolean(String(r.visual_brief || '').trim())],
      ['KHÔNG chứa cụm bị cấm',
        (r, c) => {
          const kiem = require('../src/services/kiem-kich-ban.service')
          const cam = c.input.brand.rangBuocKhongDuocNoi
          return !['loi_doc', 'caption', 'visual_brief']
            .some((t) => kiem.timViPham(String(r[t] || ''), cam).viPham)
        }],
      ['lời đọc không dài quá mức đọc được trong một nhịp',
        (r) => String(r.loi_doc || '').length <= 400],
      ['visual_brief KHÔNG tả nhận dạng người',
        // Hệ thống sinh ảnh neo nhất quán vào ảnh sản phẩm thật; nhân vật
        // không có gì để neo nên mỗi cảnh sẽ ra một người khác, mà
        // `scene_continuity` không bắt được (nó chỉ xét cỡ sản phẩm, góc
        // máy, tông màu, ánh sáng).
        (r) => !/khuôn mặt|gương mặt|mái tóc|tóc (dài|ngắn|búi|xoăn)|\b\d{2}\s*tuổi|mặc áo|trang phục|ngoại hình/i
          .test(String(r.visual_brief || ''))],
    ],
  },
]

module.exports = { CASES }
