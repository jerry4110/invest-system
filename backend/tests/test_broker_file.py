"""T-05 수용 기준: 잔고 파일 파싱(헤더 감지·컬럼 매핑), 실패 격리, 폴더 스캔."""
from pathlib import Path

import pytest

from backend.adapters.broker.file_upload import ParseError, parse_balance_file
from backend.infra import db as db_mod


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    return db_mod.get_session


CSV_STANDARD = """종목명,종목코드,보유수량,매입평균가,매입금액,현재가,평가금액,평가손익,수익률
삼성전자,005930,100,70000,7000000,75000,7500000,500000,7.14
NVIDIA,NVDA,10,120.5,1205,180.25,1802.5,597.5,49.59
"""

CSV_WITH_JUNK = """계좌번호: ***-**-1234,,,,,,,,
조회일시: 2026-07-12 08:00,,,,,,,,
,,,,,,,,
종목명,종목코드,보유수량,매입평균가,매입금액,현재가,평가금액,평가손익,수익률
삼성전자,005930,100,"70,000","7,000,000","75,000","7,500,000","500,000",7.14
"""

CSV_CUSTOM_HEADERS = """이름,티커,잔고수량,평단가,매수금액,현재가격,평가액,손익,수익률(%)
카카오,035720,50,40000,2000000,42000,2100000,100000,5.0
"""


def _w(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8-sig")
    return p


def test_parse_standard_csv(tmp_path):
    holdings = parse_balance_file(_w(tmp_path, "잔고.csv", CSV_STANDARD))
    assert len(holdings) == 2
    h = holdings[0]
    assert h.name == "삼성전자" and h.ticker == "005930"
    assert float(h.qty) == 100 and float(h.avg_price) == 70000
    assert float(h.eval_amount) == 7500000


def test_header_row_detection_and_comma_numbers(tmp_path):
    """상단 잡음 행 + 천단위 콤마 처리."""
    holdings = parse_balance_file(_w(tmp_path, "잔고2.csv", CSV_WITH_JUNK))
    assert len(holdings) == 1
    assert float(holdings[0].buy_amount) == 7000000


def test_custom_column_mapping(tmp_path):
    mapping = {"name": "이름", "ticker": "티커", "qty": "잔고수량", "avg_price": "평단가",
               "buy_amount": "매수금액", "cur_price": "현재가격", "eval_amount": "평가액",
               "pnl_amount": "손익", "pnl_pct": "수익률(%)"}
    holdings = parse_balance_file(_w(tmp_path, "c.csv", CSV_CUSTOM_HEADERS), mapping=mapping)
    assert holdings[0].name == "카카오" and float(holdings[0].qty) == 50


def test_unparseable_file_raises_clear_error(tmp_path):
    with pytest.raises(ParseError, match="컬럼"):
        parse_balance_file(_w(tmp_path, "bad.csv", "완전히,다른,파일\n1,2,3\n"))


def test_import_and_scan(session, tmp_path, monkeypatch):
    """폴더 스캔: 새 파일 자동 인식·업서트, 재스캔 시 중복 처리 안 함 (D-013)."""
    from backend.services import portfolio_service
    from backend.infra.schema import Holding

    watch = tmp_path / "downloads"
    watch.mkdir()
    _w(watch, "미래에셋_잔고_20260712.csv", CSV_STANDARD)

    n = portfolio_service.scan_watch_folder(str(watch))
    assert n == 1
    with session() as s:
        rows = s.query(Holding).all()
        assert len(rows) == 2
        assert all(r.as_of is not None for r in rows)     # NFR-04

    assert portfolio_service.scan_watch_folder(str(watch)) == 0  # 중복 방지

    _w(watch, "미래에셋_잔고_20260713.csv", CSV_STANDARD.replace("75000", "76000"))
    assert portfolio_service.scan_watch_folder(str(watch)) == 1  # 새 파일은 처리


def test_parse_failure_keeps_old_data(session, tmp_path):
    from backend.services import portfolio_service
    from backend.infra.schema import Holding

    watch = tmp_path / "dl"; watch.mkdir()
    _w(watch, "잔고_ok.csv", CSV_STANDARD)
    portfolio_service.scan_watch_folder(str(watch))
    _w(watch, "잔고_broken.csv", "엉망,파일\n1,2\n")
    portfolio_service.scan_watch_folder(str(watch))       # 예외 없이 격리
    with session() as s:
        assert s.query(Holding).count() == 2              # 기존 데이터 유지


def test_upload_and_column_map_api(session, tmp_path):
    """T-05 API: 파일 업로드·컬럼 매핑 저장/조회."""
    from fastapi.testclient import TestClient
    from backend import main as main_mod

    client = TestClient(main_mod.create_app())
    r = client.post("/api/portfolio/upload",
                    files={"file": ("잔고.csv", CSV_STANDARD.encode("utf-8-sig"), "text/csv")})
    assert r.status_code == 200 and r.json()["imported"] == 2

    r = client.put("/api/portfolio/column-map", json={"name": "이름", "qty": "잔고수량"})
    assert r.status_code == 200
    assert client.get("/api/portfolio/column-map").json()["name"] == "이름"

    r = client.post("/api/portfolio/upload",
                    files={"file": ("bad.csv", b"x,y\n1,2\n", "text/csv")})
    assert r.status_code == 422 and "컬럼" in r.json()["detail"]
