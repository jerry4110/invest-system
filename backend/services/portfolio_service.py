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
    save_snapshot()  # 전일 대비 기반 (FR-02-02)
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


def scan_watch_folder(folder: str, force: bool = False) -> int:
    """감시 폴더 스캔 (FR-03-01, D-013). force=True면 처리 이력 무시하고 재처리."""
    return scan_watch_folder_detail(folder, force=force)["imported"]


def scan_watch_folder_detail(folder: str, force: bool = False) -> dict:
    """스캔 상세 보고 — 파일별 imported/skipped/failed 사유 포함 (진단용).

    실패는 격리 — 한 파일의 실패가 스캔 전체·기존 데이터를 해치지 않는다.
    ParseError 외 예외(인코딩·라이브러리 등)도 격리하고 사유를 기록한다.
    """
    p = Path(folder)
    if not p.is_dir():
        return {"imported": 0, "files": [], "error": f"폴더 없음: {folder}"}
    imported, files = 0, []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        if f.name.startswith("~$"):  # 엑셀 임시 잠금 파일
            continue
        if not any(k in f.name.lower() or k in f.name for k in FILE_PATTERNS):
            continue
        key = f"{f.name}:{f.stat().st_mtime_ns}"
        if not force and key in _processed():
            files.append({"file": f.name, "status": "skipped", "reason": "이미 처리됨"})
            continue
        try:
            n = import_balance_file(f)
            imported += 1
            files.append({"file": f.name, "status": "imported", "holdings": n})
        except ParseError as e:
            logger.warning("잔고 파일 파싱 실패(격리): %s — %s", f.name, e)
            files.append({"file": f.name, "status": "failed", "reason": str(e)})
        except Exception as e:
            logger.warning("잔고 파일 처리 오류(격리): %s — %s", f.name, e)
            files.append({"file": f.name, "status": "failed", "reason": f"{type(e).__name__}: {e}"})
        finally:
            _mark_processed(key)  # 동일 파일 반복 시도 방지 (force 또는 파일 수정 시 재시도)
    return {"imported": imported, "files": files}


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
    save_snapshot()


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


def save_snapshot() -> None:
    """오늘 자산 스냅샷 업서트 (FR-02-02 전일 대비의 기반). 잔고·예수금 변경 시 호출."""
    from datetime import date
    from backend.infra.schema import AssetSnapshot

    d = get_holdings()
    t = d["totals"]
    with get_session() as s:
        row = s.query(AssetSnapshot).filter_by(date=date.today()).first()
        if row is None:
            row = AssetSnapshot(date=date.today(), total_asset=0, total_buy=0,
                                total_eval=0, total_pnl=0, total_cash=0)
            s.add(row)
        row.total_asset, row.total_buy = t["total_asset"], t["buy_amount"]
        row.total_eval, row.total_pnl = t["eval_amount"], t["pnl_amount"]
        row.total_cash, row.as_of = t["cash"], datetime.now()
        s.commit()


def get_summary() -> dict:
    """대시보드 자산 요약 (FR-02-01~03)."""
    from datetime import date, timedelta
    from backend.infra.schema import AssetSnapshot

    d = get_holdings()
    t = d["totals"]

    day_change = None
    with get_session() as s:
        prev = (s.query(AssetSnapshot)
                .filter(AssetSnapshot.date < date.today())
                .order_by(AssetSnapshot.date.desc()).first())
    if prev and float(prev.total_asset):
        diff = t["total_asset"] - float(prev.total_asset)
        day_change = {"amount": diff,
                      "pct": round(diff / float(prev.total_asset) * 100, 2),
                      "vs_date": prev.date.isoformat()}

    domestic = sum(h["eval_amount"] for h in d["holdings"] if h["market"] == "KRX")
    overseas = sum(h["eval_amount"] for h in d["holdings"] if h["market"] != "KRX")
    total = t["total_asset"]
    composition = []
    for label, v in (("국내주식", domestic), ("해외주식", overseas), ("현금", t["cash"])):
        if total:
            composition.append({"label": label, "amount": v,
                                "pct": round(v / total * 100, 2)})

    return {
        "total_asset": t["total_asset"], "total_buy": t["buy_amount"],
        "total_eval": t["eval_amount"], "total_pnl": t["pnl_amount"],
        "total_pnl_pct": t["pnl_pct"], "total_cash": t["cash"],
        "day_change": day_change, "composition": composition,
        "as_of": d["as_of"] or datetime.now().isoformat(timespec="seconds"),
    }
