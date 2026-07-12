# 개인투자관리시스템 (invest-system)

Phase 1 — T-01 골격. 상세: `../PRD_Phase1.md`, 개발 원칙: `../config/constitution.md`

## 요구 환경
- Python 3.12+, Node.js 20+

## 최초 설치
```bash
# 백엔드 (invest-system/ 에서)
pip install fastapi uvicorn sqlalchemy pydantic pyyaml pytest httpx cryptography keyring yfinance pandas

# 프론트엔드
cd frontend && npm install
```

## 실행 (개발)
터미널 2개:
```bash
# 1) 백엔드 — invest-system/ 에서
python -m uvicorn backend.main:app --port 8000 --reload

# 2) 프론트엔드 — invest-system/frontend 에서
npm run dev
```
브라우저에서 http://localhost:5173 접속 → 대시보드에 "✅ 백엔드 연결됨"이 보이면 정상.

## 테스트
```bash
python -m pytest backend/tests -q
```

## 구조
- `backend/` — FastAPI (api/ 라우터, services/ 로직, domain/ 계산, adapters/ 외부연동, infra/ DB·설정)
- `frontend/` — React (Vite + TypeScript), `/api`는 8000 포트로 프록시
- `data/` — SQLite DB·로그·백업 (git 제외)

## 규칙 (요약)
- API 키는 코드·config.yaml에 절대 넣지 않는다 (설정 페이지에서 암호화 저장 — T-02)
- 비즈니스 로직은 backend/services·domain에만 (React·라우터에 넣지 않음)
- 커밋 전 pytest 통과 필수 (TDD — constitution §2.8)
