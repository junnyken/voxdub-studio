# Kéo một bản sao lưu đầy đủ về máy Windows đang chạy script này (mini-spec
# V48). Bản PowerShell của `backup-pull.sh` — cùng ràng buộc, khác vỏ.
#
# Vì sao có bản riêng cho Windows: máy của chủ dự án chạy Windows (chính app
# desktop cũng chỉ chạy Windows), mà Windows KHÔNG có `cron` lẫn `bash`. Đặt
# `backup-pull.sh` vào Task Scheduler là đặt một thứ không chạy được — sao lưu
# giả vờ còn tệ hơn không có sao lưu, vì không ai đi kiểm lại.
#
#   $env:VOXDUB_ADMIN_TOKEN="..."; .\backup-pull.ps1 [thư-mục-đích] [số-bản-giữ]
#
# Đặt lịch hằng ngày 3h sáng bằng Task Scheduler — xem
# `docs/DEPLOY_RUNBOOK.md` mục 7b để có nguyên câu lệnh.

param(
    [string]$DestDir = ".\backups",
    [int]$Keep = 14
)

$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:VOXDUB_BASE_URL) { $env:VOXDUB_BASE_URL }
           else { "https://voxdub-app.cmc-1.vibenode.matbao.ai" }

if (-not $env:VOXDUB_ADMIN_TOKEN) {
    Write-Error "Thiếu VOXDUB_ADMIN_TOKEN (biến môi trường ADMIN_TOKEN của máy chủ)."
    exit 1
}

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Tmp = Join-Path $DestDir ".voxdub-backup-$Stamp.part"
$Out = Join-Path $DestDir "voxdub-backup-$Stamp.ndjson.gz"

# -UseBasicParsing để chạy được cả trên Windows PowerShell 5.1 không có IE
# engine; -TimeoutSec cao vì dump lớn thì stream lâu.
try {
    Invoke-WebRequest -Uri "$BaseUrl/v1/admin/backup" `
        -Headers @{ "X-Admin-Token" = $env:VOXDUB_ADMIN_TOKEN } `
        -OutFile $Tmp -UseBasicParsing -TimeoutSec 900 | Out-Null
}
catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Error "Sao lưu THẤT BẠI (HTTP $code): $($_.Exception.Message)"
    Remove-Item $Tmp -ErrorAction SilentlyContinue
    exit 1
}

# Giải nén THẬT trước khi đặt tên chính thức. File .gz hỏng mà vẫn nằm trong
# thư mục sao lưu là kiểu hỏng tệ nhất: chỉ phát hiện đúng lúc cần khôi phục.
# Đọc theo dòng chứ không nạp cả file vào RAM — dump có thể lớn hơn RAM.
$lines = 0
$gzipError = $null
try {
    $fs = [System.IO.File]::OpenRead($Tmp)
    $gz = New-Object System.IO.Compression.GzipStream(
        $fs, [System.IO.Compression.CompressionMode]::Decompress)
    $sr = New-Object System.IO.StreamReader($gz)
    while ($null -ne $sr.ReadLine()) { $lines++ }
}
catch {
    $gzipError = $_.Exception.Message
}
finally {
    # Phải đóng stream TRƯỚC khi xoá/đổi tên file, nếu không Windows khoá file
    # và cả hai thao tác đều hỏng (khác Linux). Dọn dẹp nằm sau khối này chứ
    # không nằm trong catch, vì `exit` trong catch bỏ qua chính phần đóng
    # stream ở đây — để lại file .part bị khoá.
    if ($sr) { $sr.Dispose() }
    if ($gz) { $gz.Dispose() }
    if ($fs) { $fs.Dispose() }
}

if ($gzipError) {
    Remove-Item $Tmp -Force -ErrorAction SilentlyContinue
    Write-Error "File tải về không phải gzip hợp lệ, bỏ: $gzipError"
    exit 1
}

if ($lines -lt 1) {
    Remove-Item $Tmp -Force -ErrorAction SilentlyContinue
    Write-Error "Bản sao lưu rỗng, bỏ."
    exit 1
}

Move-Item -Force $Tmp $Out
# Đổi đơn vị theo cỡ thật: database nhỏ mà in "0 MB" thì đọc y như sao lưu
# rỗng, và người ta sẽ đi tìm lỗi ở chỗ không có lỗi. Đã gặp thật khi chạy
# lần đầu 18-08 (7.8 KB → "0 MB").
$bytes = (Get-Item $Out).Length
$size = if ($bytes -ge 1MB) { "$([math]::Round($bytes / 1MB, 1)) MB" }
        elseif ($bytes -ge 1KB) { "$([math]::Round($bytes / 1KB, 1)) KB" }
        else { "$bytes byte" }
Write-Output "OK: $Out ($size, $lines dòng)"

# Xoay vòng: giữ lại $Keep bản mới nhất.
Get-ChildItem -Path $DestDir -Filter "voxdub-backup-*.ndjson.gz" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Keep |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Output "đã xoá bản cũ: $($_.Name)"
    }
