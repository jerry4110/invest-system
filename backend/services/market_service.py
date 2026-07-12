"""시장지표 수집 서비스 (F-00). 재시도 3회, 실패 격리(FR-00-08), as_of 기록(NFR-04)."""
import logging
import time
from datetime import datetime
from typing import Callable

from backend.adapters.market import yahoo
from backend.adapters.market.indicators import INDICATORS
from backend.infra.db import get_session
from backend.infra.schema import MarketIndicator

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
Fetcher = Callable[[], list]  # () -> [(date, value)]


def _default_fetchers(days: int = 30) -> dict[str, Fetcher]:
    return {code: (lambda s=spec.symbol: yahoo.fetch_series(s, days))
            for code, spec in INDICATORS.items()}


def _fetch_with_retry(code: str, fetcher: Fetcher) -> list | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fetcher()
        except Exception as e:
            logger.warning("지표 %s 수집 실패 (%d/%d): %s", code, attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(0.2 * attempt)
    return None


def collect_all(fetchers: dict[str, Fetcher] | None = None) -> dict:
    """전 지표 수집·업서트. 개별 실패는 격리하고 기존 데이터를 유지한다."""
    fetchers = fetchers or _default_fetchers()
    now = datetime.now()
    ok, failed = 0, []
    for code, spec in INDICATORS.items():
        series = _fetch_with_retry(code, fetchers[code])
        if series is None:
            failed.append(code)
            continue
        _upsert(code, spec.name, series, now)
        ok += 1
    return {"ok": ok, "failed": failed, "as_of": now.isoformat(timespec="seconds")}


def _upsert(code: str, name: str, series: list, as_of: datetime) -> None:
    with get_session() as s:
        existing = {r.date: r for r in s.query(MarketIndicator).filter_by(code=code).all()}
        prev_val = None
        for d, v in series:
            change = round((v - prev_val) / prev_val * 100, 4) if prev_val else 0.0
            row = existing.get(d)
            if row:
                row.value, row.change_pct, row.as_of, row.name = v, change, as_of, name
            else:
                s.add(MarketIndicator(code=code, name=name, date=d, value=v,
                                      change_pct=change, as_of=as_of))
            prev_val = v
        s.commit()


def get_latest() -> list[dict]:
    """지표별 최신값 + 최근 30일 스파크라인 (FR-02-13)."""
    out = []
    with get_session() as s:
        for code, spec in INDICATORS.items():
            rows = (s.query(MarketIndicator).filter_by(code=code)
                    .order_by(MarketIndicator.date.desc()).limit(30).all())
            if not rows:
                continue
            latest = rows[0]
            out.append({
                "code": code, "name": spec.name, "category": spec.category,
                "value": latest.value, "change_pct": latest.change_pct,
                "date": latest.date.isoformat(),
                "as_of": latest.as_of.isoformat(timespec="seconds"),
                "spark": [r.value for r in reversed(rows)],
            })
    return out
