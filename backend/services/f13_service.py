"""13F 서비스 (M7-3) — 기관 등록·조회·갱신 알림."""
import json
import logging
from datetime import datetime

from backend.adapters.market.edgar import classify_changes, fetch_two_filings, parse_infotable
from backend.infra.db import get_session
from backend.infra.schema import AppSetting, Institution

logger = logging.getLogger(__name__)
DEFAULT_INSTITUTIONS = [("버크셔 해서웨이 (Berkshire Hathaway)", "1067983")]


def _fetch_two_filings(cik: str):
    return fetch_two_filings(cik)


def list_institutions() -> list[dict]:
    with get_session() as s:
        if s.query(Institution).count() == 0:
            for name, cik in DEFAULT_INSTITUTIONS:
                s.add(Institution(name=name, cik=cik))
            s.commit()
        rows = s.query(Institution).all()
    return [{"id": r.id, "name": r.name, "cik": r.cik} for r in rows]


def add_institution(name: str, cik: str) -> None:
    if not cik.isdigit():
        raise ValueError("CIK는 숫자여야 합니다 (SEC EDGAR에서 확인)")
    with get_session() as s:
        s.add(Institution(name=name, cik=cik))
        s.commit()


def get_portfolio(cik: str) -> dict:
    """상위 10 보유 + 분기 변동 (FR-07-21). 새 공시 감지 시 알림 (FR-07-23)."""
    latest, prev = _fetch_two_filings(cik)
    holdings = parse_infotable(latest["xml"])
    changes = (classify_changes(holdings, parse_infotable(prev["xml"]))
               if prev else [])

    seen_key = f"13f_last_seen_{cik}"
    with get_session() as s:
        row = s.get(AppSetting, seen_key)
        if row is None or row.value != latest["accession"]:
            from backend.services.alert_service import create_alert
            inst = next((i["name"] for i in list_institutions() if i["cik"].lstrip("0") == cik.lstrip("0")), cik)
            create_alert("13f_update", f"{inst} 13F 갱신 ({latest['period']})",
                         f"상위: {', '.join(h['issuer'] for h in holdings[:3])}")
            s.merge(AppSetting(key=seen_key, value=latest["accession"]))
            s.commit()

    return {"cik": cik, "period": latest["period"],
            "top_holdings": holdings[:10],
            "changes": [c for c in changes if c["change"] != "유지"][:20] +
                       [c for c in changes if c["change"] == "유지"][:5],
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "source": "SEC EDGAR (13F-HR)"}
