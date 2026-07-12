"""T-22 수용 기준: DART 3개년 재무(국내), yfinance(해외), 티커 라우팅, 키 부재 안내."""
import io
import json
import zipfile

import pytest

from backend.infra import db as db_mod


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))


def _corp_zip() -> bytes:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code></list>
  <list><corp_code>00164742</corp_code><corp_name>SK하이닉스</corp_name><stock_code>000660</stock_code></list>
  <list><corp_code>99999999</corp_code><corp_name>비상장사</corp_name><stock_code> </stock_code></list>
</result>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("CORPCODE.xml", xml)
    return buf.getvalue()


def _fin_json(year: int, rev: int) -> bytes:
    rows = [
        {"account_nm": "매출액", "fs_div": "CFS", "thstrm_amount": f"{rev:,}"},
        {"account_nm": "영업이익", "fs_div": "CFS", "thstrm_amount": f"{rev // 10:,}"},
        {"account_nm": "당기순이익", "fs_div": "CFS", "thstrm_amount": f"{rev // 20:,}"},
        {"account_nm": "매출액", "fs_div": "OFS", "thstrm_amount": "1"},  # 별도 — 무시돼야 함
    ]
    return json.dumps({"status": "000", "list": rows}).encode()


def make_fake_fetch():
    def fetch(url: str) -> bytes:
        if "corpCode" in url:
            return _corp_zip()
        if "fnlttSinglAcnt" in url:
            year = int(url.split("bsns_year=")[1][:4])
            return _fin_json(year, {2025: 300_000, 2024: 258_000, 2023: 200_000}[year] * 10**8)
        raise AssertionError(f"unexpected url {url}")
    return fetch


def test_dart_financials_3years(fresh, monkeypatch):
    """FR-04-01: 최근 3년 매출·영업이익·순이익 (연결 CFS 기준)."""
    from backend.services import settings_service
    settings_service.set_secret("dart_api_key", "TESTKEY")
    from backend.adapters.market.dart import DartClient

    c = DartClient(fetch=make_fake_fetch(), latest_year=2025)
    fin = c.get_major_financials("005930")
    assert [f["year"] for f in fin] == [2023, 2024, 2025]
    assert fin[-1]["revenue"] == 300_000 * 10**8
    assert fin[-1]["operating_profit"] == 30_000 * 10**8
    assert fin[-1]["net_income"] == 15_000 * 10**8


def test_dart_key_missing_message(fresh):
    from backend.adapters.market.dart import DartClient
    with pytest.raises(RuntimeError, match="dart_api_key"):
        DartClient(fetch=make_fake_fetch()).get_major_financials("005930")


def test_dart_unknown_ticker(fresh):
    from backend.services import settings_service
    settings_service.set_secret("dart_api_key", "TESTKEY")
    from backend.adapters.market.dart import DartClient
    with pytest.raises(ValueError, match="종목코드"):
        DartClient(fetch=make_fake_fetch(), latest_year=2025).get_major_financials("999999")


def test_router_domestic_vs_overseas(fresh, monkeypatch):
    """국내(숫자 코드) → DART, 해외 → yfinance."""
    from backend.services import financials_service

    monkeypatch.setattr(financials_service, "_dart_financials",
                        lambda t: [{"year": 2025, "revenue": 1, "operating_profit": 1, "net_income": 1}])
    monkeypatch.setattr(financials_service, "_yahoo_financials",
                        lambda t: [{"year": 2025, "revenue": 2, "operating_profit": 2, "net_income": 2}])
    assert financials_service.get_financials("005930")["source"] == "DART"
    assert financials_service.get_financials("NVDA")["source"] == "yfinance"
    assert financials_service.get_financials("NVDA")["financials"][0]["revenue"] == 2
    assert financials_service.get_financials("005930")["as_of"]   # NFR-04
