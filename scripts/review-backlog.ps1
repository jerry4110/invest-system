# 소급 Codex 리뷰 (PowerShell): 모든 기존 커밋을 오래된 순으로 리뷰
# 실행: invest-system 폴더에서  .\scripts\review-backlog.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
New-Item -ItemType Directory -Force -Path reviews | Out-Null
$commits = git rev-list --reverse HEAD
foreach ($c in $commits) {
  $hash = git rev-parse --short $c
  $out = "reviews/$hash.md"
  if (Test-Path $out) { Write-Host "[skip] $hash (이미 리뷰됨)"; continue }
  $subject = git log -1 --pretty=%s $c
  Write-Host "[review] $hash $subject"
  $prompt = @"
너는 시니어 코드 리뷰어다. stdin의 git 커밋 diff를 리뷰하라.
프로젝트 규칙: TDD 필수, 비즈니스 로직은 services/domain에만, 민감정보 평문 금지,
모든 조회 데이터에 as_of, 어댑터 패턴 준수.
출력 형식(한국어 Markdown):
## 요약 (1-2문장)
## 이슈
- [Critical|Major|Minor] 파일:라인 — 문제와 수정 제안
## 잘한 점 (1-2개)
Critical/Major가 없으면 '## 이슈' 아래 '없음'이라고 써라.
"@
  git show $c --stat --patch | codex exec --sandbox read-only $prompt | Out-File -Encoding utf8 $out
  if ((Get-Item $out).Length -gt 0) {
    $header = "# Codex Review — $hash $subject`n"
    $header + (Get-Content $out -Raw) | Out-File -Encoding utf8 $out
    git notes add -f -F $out $c 2>$null
    Write-Host "  → $out"
  } else { Remove-Item $out; Write-Host "  → 실패(인증 확인 필요)" }
}
Write-Host "완료. reviews/ 폴더를 확인하세요."
