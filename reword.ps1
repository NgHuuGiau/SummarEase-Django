$f = $args[0]
$content = Get-Content $f
$content = $content -replace '^pick 9f11676.*', 'reword 9f11676 feat: E2E Playwright tests + Locust load testing'
$content = $content -replace '^pick 45fad13.*', 'reword 45fad13 Cứng hóa production: rate limit, metrics, API docs, test backup restore'
$content = $content -replace '^pick 56b053c.*', 'reword 56b053c Đóng coverage gaps tới 99-100% + CI smoke'
$content = $content -replace '^pick ef364a8.*', 'reword ef364a8 Hoàn thiện đợt 2: health check thật, cache TextRank, JSON logging, Dockerfile non-root + healthcheck, backup_db, login lockout, password reset demo, Gemini toggle, tách CSS 6 file, + test W001/backup/urls/health degrade, cập nhật tài liệu'
Set-Content $f $content