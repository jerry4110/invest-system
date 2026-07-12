"""DART Open API 어댑터 (FR-00-04, FR-04-01) — 국내 기업 3개년 주요 재무.

키: secret_store의 dart_api_key (설정 페이지에서 등록). fetch 주입으로 테스트 격리.
"""
import io
import logging
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

logger = logging.getLogger(__name__)

BASE = "https://opendart.fss.or.kr/api"
_ACCOUNTS = {"매출액": "revenue", "영업이익": "operating_profit", "당기순이익": "net_income"}
_corp_cache: dict[str, str] | None = None  # stock_code → corp_code


def _default_fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as res:
        return res.read()


class DartClient:
    def __init__(self, fetch=None, latest_year: int | None = None):
        self._fetch = fetch or _default_fetch
        # 사업보고서는 통상 3월 제출 — 4월 전이면 2년 전이 최신 확정연도
        today = date.today()
        self._latest = latest_year or (today.year - 1 if today.month >= 4 else today.year - 2)

    def _key(self) -> str:
        from backend.services.settings_service import get_secret
        key = get_secret("dart_api_key")
        if not key:
            raise RuntimeError("dart_api_key가 없습니다 — 설정 > API 키에 등록하세요")
        return key

    def _corp_map(self) -> dict[str, str]:
        global _corp_cache
        if _corp_cache is None:
            raw = self._fetch(f"{BASE}/corpCode.xml?crtfc_key={self._key()}")
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                xml = z.read(z.namelist()[0])
            mapping = {}
            for el in ET.fromstring(xml).iter("list"):
                stock = (el.findtext("stock_code") or "").strip()
                if stock:
                    mapping[stock] = (el.findtext("corp_code") or "").strip()
            _corp_cache = mapping
            logger.info("DART corp_code 매핑 로드: %d개 상장사", len(mapping))
        return _corp_cache

    def get_major_financials(self, stock_code: str, years: int = 3) -> list[dict]:
        """최근 N년 매출·영업이익·순이익 (연결 CFS 우선). 연도 오름차순."""
        import json
        corp = self._corp_map().get(stock_code)
        if not corp:
            raise ValueError(f"DART에서 종목코드 {stock_code}를 찾지 못했습니다")
        out = []
        for year in range(self._latest - years + 1, self._latest + 1):
            url = (f"{BASE}/fnlttSinglAcnt.json?crtfc_key={self._key()}"
                   f"&corp_code={corp}&bsns_year={year}&reprt_code=11011")
            body = json.loads(self._fetch(url))
            if body.get("status") != "000":
                logger.warning("DART %d년 재무 없음: %s", year, body.get("message"))
                continue
            row = {"year": year}
            for item in body.get("list", []):
                field = _ACCOUNTS.get(item.get("account_nm", "").strip())
                if field and item.get("fs_div") == "CFS" and field not in row:
                    row[field] = int(str(item["thstrm_amount"]).replace(",", "") or 0)
            if len(row) > 1:
                out.append(row)
        return out
