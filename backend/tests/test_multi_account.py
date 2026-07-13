"""실제 #Stock_Balance 포맷 대응 (2026-07-13 파일 검증) — cp949·A코드·현금성·USD 환산·파일명=계좌."""
from datetime import date, datetime

import pytest

from backend.infra import db as db_mod
from backend.infra.schema import CashBalance, Holding, MarketIndicator

FORMAT_B = """유형,종목번호,종목명,구분,보유량,평균단가,현재가,매입금액,평가금액,평가손익,수익률
주식,A005930,삼성전자,현금,160,276007,254500,44161184,40720000,-3441184,-7.79
주식,A0091P0,TIGER 코리아원자력,현금,266,13405,14745,3565859,3922170,356311,9.99
통화,USD,미국달러,현금,13056.23,0,0,13056.23,13056.23,0,0
원화RP,CMARPC01,CMA RP_개인,현금,34384,1,0,34384,34405,21,0.06
해외주식,MU,마이크론 테크놀로지,현금,3,952.27,927.01,2856.82,2781.03,-75.79,-2.65
,,,,,,,,,,
"""

FORMAT_A_IRP = """종목명,보유량,매입금액,평가금액,평가손익,수익률,운용비율
미래에셋증권현금성자산,160053,0,160053,0,0.00,0.30
KODEX AI전력핵심설비,348,8602017,12980400,4378383,50.90,23.50
"""


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    with db_mod.get_session() as s:   # 환율 시드 (T-03 수집분)
        s.add(MarketIndicator(code="USDKRW", name="원/달러", date=date.today(),
                              value=1400.0, change_pct=0, as_of=datetime.now()))
        s.commit()
    return tmp_path


def _w(tmp_path, name, text, enc="cp949"):
    p = tmp_path / name
    p.write_bytes(text.encode(enc))
    return p


def test_cp949_format_b_parsing(fresh):
    """cp949 + A코드 정규화 + 유형 기반 시장 분류 + 현금성 분리."""
    from backend.adapters.broker.file_upload import parse_balance_file
    holdings = parse_balance_file(_w(fresh, "주식계좌 9325.csv", FORMAT_B))
    by = {h.ticker: h for h in holdings}
    assert "005930" in by                              # A005930 → 005930
    assert "0091P0" in by and by["0091P0"].market == "KRX"
    assert by["MU"].market == "OVERSEAS"               # 유형=해외주식
    assert "USD" not in by and "CMARPC01" not in by    # 현금성은 보유종목에서 제외


def test_import_converts_usd_and_cash(fresh):
    """해외주식 USD→원화 환산(등록 환율), 현금성(원화RP·통화)→예수금."""
    from backend.services import portfolio_service
    path = _w(fresh, "주식계좌 9325.csv", FORMAT_B)
    portfolio_service.import_balance_file(path, account_alias="주식계좌 9325")
    with db_mod.get_session() as s:
        mu = s.query(Holding).filter_by(ticker="MU").one()
        assert float(mu.eval_amount) == pytest.approx(2781.03 * 1400, rel=1e-4)
        assert mu.pnl_pct == pytest.approx(-2.65, abs=0.01)   # 수익률은 원본 유지
        cash = {c.currency: float(c.amount) for c in s.query(CashBalance).all()}
        assert cash["KRW"] == pytest.approx(34405)             # RP 평가금액
        assert cash["USD"] == pytest.approx(13056.23)
    totals = portfolio_service.get_holdings()["totals"]
    assert totals["cash"] == pytest.approx(34405 + 13056.23 * 1400, rel=1e-4)


def test_format_a_irp_without_price_columns(fresh):
    """IRP 포맷: 단가·현재가 없음 → 계산 보완, 현금성자산 행 → 예수금."""
    from backend.services import portfolio_service
    path = _w(fresh, "IRP계좌.csv", FORMAT_A_IRP)
    portfolio_service.import_balance_file(path, account_alias="IRP계좌")
    with db_mod.get_session() as s:
        h = s.query(Holding).one()                     # 현금성자산 제외 → 1종목
        assert h.name.startswith("KODEX AI")
        assert float(h.avg_price) == pytest.approx(8602017 / 348, rel=1e-4)
        assert h.pnl_pct == pytest.approx(50.90, abs=0.01)
        cash = s.query(CashBalance).one()
        assert float(cash.amount) == pytest.approx(160053)


def test_scan_dedicated_folder_filename_is_account(fresh):
    """전용 폴더: 패턴 무관 전체 스캔, 파일명(확장자 제외)=계좌명 (D-020)."""
    from backend.services import portfolio_service
    from backend.infra.schema import Account
    watch = fresh / "#Stock_Balance"
    watch.mkdir()
    _w(watch, "주식계좌 9325.csv", FORMAT_B)
    _w(watch, "IRP계좌.csv", FORMAT_A_IRP)
    n = portfolio_service.scan_watch_folder(str(watch))
    assert n == 2
    with db_mod.get_session() as s:
        aliases = {a.alias for a in s.query(Account).all()}
        assert aliases == {"주식계좌 9325", "IRP계좌"}
    port = portfolio_service.get_holdings()
    accounts = {h["account"] for h in port["holdings"]}
    assert accounts == {"주식계좌 9325", "IRP계좌"}


def test_reset_wipes_all_and_allows_rescan(fresh):
    """전체 초기화: 보유·현금·계좌·처리이력 삭제 → 재스캔으로 재적재."""
    from fastapi.testclient import TestClient
    from backend import main as main_mod
    from backend.services import portfolio_service
    from backend.infra.schema import Account

    watch = fresh / "dl"
    watch.mkdir()
    _w(watch, "IRP계좌.csv", FORMAT_A_IRP)
    portfolio_service.scan_watch_folder(str(watch))

    client = TestClient(main_mod.create_app())
    assert client.post("/api/portfolio/reset").status_code == 200
    with db_mod.get_session() as s:
        assert s.query(Holding).count() == 0
        assert s.query(CashBalance).count() == 0
        assert s.query(Account).count() == 0
    assert portfolio_service.scan_watch_folder(str(watch)) == 1   # 처리이력도 초기화됨


def test_usd_without_rate_fails_clearly(tmp_path, monkeypatch):
    """환율 미수집 상태에서 USD 종목 → 명확한 사유로 실패 (추정 금지)."""
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    db_mod.init_db(str(tmp_path / "t.db"))
    from backend.services import portfolio_service
    path = _w(tmp_path, "주식계좌 9325.csv", FORMAT_B)
    with pytest.raises(Exception, match="환율"):
        portfolio_service.import_balance_file(path, account_alias="주식계좌 9325")
