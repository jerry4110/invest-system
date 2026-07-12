"""포트폴리오 서비스 (F-03) — 잔고 파일 임포트·폴더 스캔 (D-013)."""
import json
import logging
from datetime import datetime
from pathlib import Path

from backend.adapters.broker.file_upload import ParseError, parse_balance_file
from backend.infra.db import get_session
from backend.infra.schema import Account, AppSetting, Holding

logger = logging.getLogger(__name__)

FILE_PATTERNS = ("잔고", "미래에셋", "balance")  # 파일명 인식 키워드
_PROCESSED_KEY = "processed_balance_files"


def get_column_mapping() -> dict | None:
    with get_session() as s:
        row = s.get(AppSetting, "broker_column_map")
    return json.loads(row.value) if row and row.value else None


def set_column_mapping(mapping: dict) -> None:
    with get_session() as s:
        s.merge(AppSetting(key="broker_column_map", value=json.dumps(mapping, ensure_ascii=False)))
        s.commit()


def _get_or_create_account(alias: str) -> int:
    with get_session() as s:
        acc = s.query(Account).filter_by(alias=alias).first()
        if not acc:
            acc = Account(broker="miraeasset", account_no_masked="file", alias=alias,
                          adapter_type="file")
            s.add(acc)
            s.commit()
        return acc.id


def import_balance_file(path: str | Path, account_alias: str = "미래에셋(파일)") -> int:
    """잔고 파일 파싱 → holding 테이블 전량 교체 업서트. as_of는 파일 수정시각."""
    path = Path(path)
    holdings = parse_balance_file(path, mapping=get_column_mapping())
    as_of = datetime.fromtimestamp(path.stat().st_mtime)
    account_id = _get_or_create_account(account_alias)
    with get_session() as s:
        s.query(Holding).filter_by(account_id=account_id).delete()
        for h in holdings:
            s.add(Holding(account_id=account_id, ticker=h.ticker, name=h.name,
                          market=h.market, qty=h.qty, avg_price=h.avg_price,
                          buy_amount=h.buy_amount, cur_price=h.cur_price,
                          eval_amount=h.eval_amount, pnl_amount=h.pnl_amount,
                          pnl_pct=h.pnl_pct, as_of=as_of))
        s.commit()
    logger.info("잔고 파일 임포트: %s (%d종목, 기준 %s)", path.name, len(holdings), as_of)
    return len(holdings)


def _processed() -> set[str]:
    with get_session() as s:
        row = s.get(AppSetting, _PROCESSED_KEY)
    return set(json.loads(row.value)) if row and row.value else set()


def _mark_processed(key: str) -> None:
    done = _processed()
    done.add(key)
    with get_session() as s:
        s.merge(AppSetting(key=_PROCESSED_KEY, value=json.dumps(sorted(done))))
        s.commit()


def scan_watch_folder(folder: str) -> int:
    """감시 폴더에서 미처리 잔고 파일을 찾아 임포트 (FR-03-01, D-013).

    실패는 격리 — 한 파일의 파싱 실패가 스캔 전체·기존 데이터를 해치지 않는다.
    """
    p = Path(folder)
    if not p.is_dir():
        return 0
    imported = 0
    for f in sorted(p.iterdir()):
        if f.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        if not any(k in f.name.lower() or k in f.name for k in FILE_PATTERNS):
            continue
        key = f"{f.name}:{f.stat().st_mtime_ns}"
        if key in _processed():
            continue
        try:
            import_balance_file(f)
            imported += 1
        except ParseError as e:
            logger.warning("잔고 파일 파싱 실패(격리): %s — %s", f.name, e)
        finally:
            _mark_processed(key)  # 실패 파일 반복 시도 방지 (수정되면 mtime 변경으로 재시도)
    return imported


def get_holdings() -> dict:
    """계좌별 보유현황 + 비중·합계·예수금 (FR-03-11, 13). as_of는 최신 잔고 기준시각."""
    from backend.infra.schema import CashBalance

    with get_session() as s:
        rows = (s.query(Holding, Account.alias)
                .join(Account, Holding.account_id == Account.id).all())
        cash_rows = s.query(CashBalance).all()

    total_eval = sum(float(h.eval_amount) for h, _ in rows)
    total_buy = sum(float(h.buy_amount) for h, _ in rows)
    total_pnl = sum(float(h.pnl_amount) for h, _ in rows)
    cash = sum(float(c.amount) for c in cash_rows)
    as_of = max((h.as_of for h, _ in rows), default=None)

    holdings = [{
        "account": alias, "name": h.name, "ticker": h.ticker, "market": h.market,
        "qty": float(h.qty), "avg_price": float(h.avg_price),
        "buy_amount": float(h.buy_amount), "cur_price": float(h.cur_price),
        "eval_amount": float(h.eval_amount), "pnl_amount": float(h.pnl_amount),
        "pnl_pct": h.pnl_pct,
        "weight_pct": round(float(h.eval_amount) / total_eval * 100, 2) if total_eval else 0.0,
        "as_of": h.as_of.isoformat(timespec="seconds"),
    } for h, alias in rows]
    holdings.sort(key=lambda x: -x["eval_amount"])

    return {
        "holdings": holdings,
        "totals": {
            "buy_amount": total_buy, "eval_amount": total_eval, "pnl_amount": total_pnl,
            "pnl_pct": round(total_pnl / total_buy * 100, 2) if total_buy else 0.0,
            "cash": cash, "total_asset": total_eval + cash,
        },
        "as_of": as_of.isoformat(timespec="seconds") if as_of else None,
    }


def set_cash(amount: float, account_alias: str = "미래에셋(파일)") -> None:
    """예수금 수기 입력 (FR-03-04). 계좌당 1행 유지."""
    from backend.infra.schema import CashBalance

    account_id = _get_or_create_account(account_alias)
    with get_session() as s:
        s.query(CashBalance).filter_by(account_id=account_id).delete()
        s.add(CashBalance(account_id=account_id, currency="KRW",
                          amount=amount, as_of=datetime.now()))
        s.commit()


def export_csv() -> str:
    """보유현황 CSV (FR-03-14)."""
    import io, csv
    data = get_holdings()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["계좌", "종목명", "종목코드", "시장", "보유수량", "평균단가",
                "매입금액", "현재가", "평가금액", "평가손익", "수익률(%)", "비중(%)", "기준시각"])
    for h in data["holdings"]:
        w.writerow([h["account"], h["name"], h["ticker"], h["market"], h["qty"],
                    h["avg_price"], h["buy_amount"], h["cur_price"], h["eval_amount"],
                    h["pnl_amount"], h["pnl_pct"], h["weight_pct"], h["as_of"]])
    t = data["totals"]
    w.writerow(["합계", "", "", "", "", "", t["buy_amount"], "", t["eval_amount"],
                t["pnl_amount"], t["pnl_pct"], 100.0, data["as_of"] or ""])
    return buf.getvalue()
