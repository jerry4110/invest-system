"""T-35 수용 기준: 13F XML 파싱·상위10·변동 분류·기관 등록·갱신 알림 (FR-07-21~23)."""
import pytest
from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.infra import db as db_mod

INFOTABLE = """<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip>
    <value>60000000</value><shrsOrPrnAmt><sshPrnamt>300000000</sshPrnamt></shrsOrPrnAmt></infoTable>
  <infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip>
    <value>20000000</value><shrsOrPrnAmt><sshPrnamt>100000000</sshPrnamt></shrsOrPrnAmt></infoTable>
  <infoTable><nameOfIssuer>BANK AMER CORP</nameOfIssuer><cusip>060505104</cusip>
    <value>30000000</value><shrsOrPrnAmt><sshPrnamt>900000000</sshPrnamt></shrsOrPrnAmt></infoTable>
  <infoTable><nameOfIssuer>CHEVRON CORP</nameOfIssuer><cusip>166764100</cusip>
    <value>10000000</value><shrsOrPrnAmt><sshPrnamt>60000000</sshPrnamt></shrsOrPrnAmt></infoTable>
</informationTable>"""

PREV_TABLE = """<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip>
    <value>90000000</value><shrsOrPrnAmt><sshPrnamt>500000000</sshPrnamt></shrsOrPrnAmt></infoTable>
  <infoTable><nameOfIssuer>BANK AMER CORP</nameOfIssuer><cusip>060505104</cusip>
    <value>30000000</value><shrsOrPrnAmt><sshPrnamt>900000000</sshPrnamt></shrsOrPrnAmt></infoTable>
  <infoTable><nameOfIssuer>KRAFT HEINZ CO</nameOfIssuer><cusip>500754106</cusip>
    <value>12000000</value><shrsOrPrnAmt><sshPrnamt>325000000</sshPrnamt></shrsOrPrnAmt></infoTable>
</informationTable>"""


def test_parse_and_aggregate_top_holdings():
    """동일 종목 합산 + 비중 + 정렬 (FR-07-21)."""
    from backend.adapters.market.edgar import parse_infotable

    holdings = parse_infotable(INFOTABLE.encode())
    assert holdings[0]["issuer"] == "APPLE INC"
    assert holdings[0]["value"] == 80_000_000            # 두 행 합산
    assert holdings[0]["shares"] == 400_000_000
    assert holdings[0]["weight_pct"] == pytest.approx(66.67, abs=0.01)  # 80M/120M
    assert len(holdings) == 3


def test_quarter_change_classification():
    """FR-07-21: 신규/청산/확대/축소."""
    from backend.adapters.market.edgar import classify_changes, parse_infotable

    cur, prev = parse_infotable(INFOTABLE.encode()), parse_infotable(PREV_TABLE.encode())
    ch = classify_changes(cur, prev)
    by = {c["issuer"]: c["change"] for c in ch}
    assert by["CHEVRON CORP"] == "신규"
    assert by["KRAFT HEINZ CO"] == "청산"
    assert by["APPLE INC"] == "축소"                     # 500M주 → 400M주
    assert by["BANK AMER CORP"] == "유지"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return TestClient(main_mod.create_app())


def test_institutions_default_and_add(client):
    """FR-07-22: 버크셔 기본 + 사용자 추가."""
    lst = client.get("/api/13f/institutions").json()
    assert any("버크셔" in i["name"] or "Berkshire" in i["name"] for i in lst)
    r = client.post("/api/13f/institutions", json={"name": "Bridgewater", "cik": "1350694"})
    assert r.status_code == 200
    assert any(i["name"] == "Bridgewater" for i in client.get("/api/13f/institutions").json())
    assert client.post("/api/13f/institutions",
                       json={"name": "bad", "cik": "abc"}).status_code == 422


def test_13f_api_with_mocked_edgar(client, monkeypatch):
    """조회 API + 신규 공시 감지 알림 (FR-07-23)."""
    from backend.services import f13_service
    from backend.infra.schema import Alert

    monkeypatch.setattr(f13_service, "_fetch_two_filings",
                        lambda cik: ({"accession": "acc-2", "period": "2026-03-31",
                                      "xml": INFOTABLE.encode()},
                                     {"accession": "acc-1", "period": "2025-12-31",
                                      "xml": PREV_TABLE.encode()}))
    body = client.get("/api/13f/1067983").json()
    assert body["top_holdings"][0]["issuer"] == "APPLE INC"
    assert len(body["top_holdings"]) <= 10
    assert body["period"] == "2026-03-31"
    changes = {c["issuer"]: c["change"] for c in body["changes"]}
    assert changes["CHEVRON CORP"] == "신규"

    body2 = client.get("/api/13f/1067983").json()          # 재조회: 같은 공시 → 알림 1회만
    with db_mod.get_session() as s:
        assert s.query(Alert).filter_by(kind="13f_update").count() == 1
