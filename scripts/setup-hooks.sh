#!/bin/sh
# 훅 활성화 (저장소에서 1회 실행): sh scripts/setup-hooks.sh
git config core.hooksPath scripts/git-hooks
echo "git hooks 경로 설정 완료 → scripts/git-hooks (post-commit: Codex 교차 리뷰)"
