# 훅 활성화 (PowerShell용, 저장소 루트에서 1회 실행): .\scripts\setup-hooks.ps1
git config core.hooksPath scripts/git-hooks
Write-Host "git hooks 경로 설정 완료 → scripts/git-hooks (post-commit: Codex 교차 리뷰)"
