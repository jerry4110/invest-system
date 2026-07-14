"""포트폴리오 서비스 (F-03) — 잔고 파일 임포트·폴더 스캔 (D-013)."""
import json
import logging
from datetime import datetime
from pathlib import Path

from backend.adapters.broker.file_upload import ParseError, parse_balance_file
from backend.infra.db import get_session
from backend.infra.schema import Account, AppSetting, Holding

logger = logging.getLogger(__name__)

# D-020: 전용 폴더(#Stock_Balance) 방식 — 폴더 내 모든 스프레드시트를 계좌 파일로 간주
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


def _latest_usdkrw() -> float | None:
    from backend.infra.schema import MarketIndicator
    with get_session() as s:
        row = (s.query(MarketIndicator).filter_by(code="USDKRW")
               .order_by(MarketIndicator.date.desc()).first())
    return row.value if row else None


def import_balance_file(path: str | Path, account_alias: str | None = None) -> int:
    """잔고 파일 파싱 → 해당 계좌의 보유·예수금 전량 교체.

    - 계좌명 = 파일명(확장자 제외), 인자로 재정의 가능 (D-020)
    - 현금성 행(통화·RP·현금성자산)은 예수금으로 분리 (KRW/USD)
    - 해외주식 USD 금액은 최신 USDKRW 지표로 원화 환산 — 환율 미수집이면 명확히 실패
    """
    from decimal import Decimal
    from backend.infra.schema import CashBalance

    path = Path(path)
    alias = account_alias or path.stem.strip()
    holdings = parse_balance_file(path, mapping=get_column_mapping())
    as_of = datetime.fromtimestamp(path.stat().st_mtime)
    account_id = _get_or_create_account(alias)

    cash_krw = sum(float(h.eval_amount) for h in holdings if h.market == "CASH_KRW")
    cash_usd = sum(float(h.eval_amount) for h in holdings if h.market == "CASH_USD")
    stock_rows = [h for h in holdings if not h.market.startswith("CASH")]

    rate = None
    if cash_usd or any(h.currency == "USD" for h in stock_rows):
        rate = _latest_usdkrw()
        if rate is None:
            raise RuntimeError(
                f"{path.name}: 해외(USD) 자산 환산에 필요한 환율(USDKRW)이 없습니다 — "
                "대시보드 '업데이트'로 시장지표를 먼저 수집하세요")

    with get_session() as s:
        s.query(Holding).filter_by(account_id=account_id).delete()
        s.query(CashBalance).filter_by(account_id=account_id, source="file").delete()
        for h in stock_rows:
            fx = Decimal(str(rate)) if h.currency == "USD" else Decimal(1)
            s.add(Holding(account_id=account_id, ticker=h.ticker, name=h.name,
                          market=h.market, sector=h.sector, qty=h.qty,
                          avg_price=h.avg_price * fx, buy_amount=h.buy_amount * fx,
                          cur_price=h.cur_price * fx, eval_amount=h.eval_amount * fx,
                          pnl_amount=h.pnl_amount * fx,
                          pnl_pct=h.pnl_pct, as_of=as_of))
        if cash_krw:
            s.add(CashBalance(account_id=account_id, currency="KRW",
                              amount=cash_krw, source="file", as_of=as_of))
        if cash_usd:
            s.add(CashBalance(account_id=account_id, currency="USD",
                              amount=cash_usd, source="file", as_of=as_of))
        s.commit()
    logger.info("잔고 임포트 [%s]: %d종목, 현금 KRW %.0f / USD %.2f",
                alias, len(stock_rows), cash_krw, cash_usd)
    save_snapshot()
    return len(stock_rows)


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
    _rate_cache = {}
    def _rate():
        if "v" not in _rate_cache:
            _rate_cache["v"] = _latest_usdkrw()
        return _rate_cache["v"]
    by_acct_cash: dict[int, list] = {}
    for c in cash_rows:
        by_acct_cash.setdefault(c.account_id, []).append(c)
    cash = sum(_effective_cash(rows_, _rate)[0] for rows_ in by_acct_cash.values())
    as_of = max((h.as_of for h, _ in rows), default=None)

    holdings = [{
        "account": alias, "name": h.name, "ticker": h.ticker, "market": h.market,
        "sector": h.sector or "", "qty": float(h.qty), "avg_price": float(h.avg_price),
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
    """예수금 수기 입력 (FR-03-04) — 수동값이 파일값보다 우선 (2026-07-14 정책)."""
    from backend.infra.schema import CashBalance

    account_id = _get_or_create_account(account_alias)
    with get_session() as s:
        s.query(CashBalance).filter_by(account_id=account_id, source="manual").delete()
        s.add(CashBalance(account_id=account_id, currency="KRW",
                          amount=amount, source="manual", as_of=datetime.now()))
        s.commit()
    save_snapshot()


def _effective_cash(cash_rows, usd_rate_getter) -> tuple[float, str]:
    """계좌의 유효 예수금(원화 환산): 수동 KRW가 있으면 파일 KRW 대체, USD는 파일값 환산."""
    manual_krw = [c for c in cash_rows if c.source == "manual" and c.currency == "KRW"]
    file_krw = [c for c in cash_rows if c.source == "file" and c.currency == "KRW"]
    usd = [c for c in cash_rows if c.currency == "USD"]
    krw = float(manual_krw[-1].amount) if manual_krw else sum(float(c.amount) for c in file_krw)
    total = krw
    for c in usd:
        rate = usd_rate_getter()
        total += float(c.amount) * (rate or 0.0)
    return total, ("manual" if manual_krw else "file")


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


# ── T-29: 분류·기간 수익률·추이 (FR-03-21~28) ──

ETF_BRANDS = ("KODEX", "TIGER", "ACE", "SOL", "PLUS", "RISE", "KBSTAR", "HANARO",
              "ARIRANG", "KOSEF", "TIMEFOLIO", "TIME ", "히어로즈", "WOORI", "BNK")


def _classify_type(name: str, market: str) -> str:
    """FR-03-22: 투자유형 — ETF(브랜드명 휴리스틱) × 국내/해외."""
    upper = name.upper()
    is_etf = any(b in upper for b in ETF_BRANDS) or "ETF" in upper
    region = "국내" if market == "KRX" else "해외"
    return f"{region} {'ETF' if is_etf else '주식'}"


def get_analysis() -> dict:
    """유형·산업별 구성 (FR-03-21~23)."""
    d = get_holdings()
    by_type: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for h in d["holdings"]:
        t = _classify_type(h["name"], h["market"])
        by_type[t] = by_type.get(t, 0) + h["eval_amount"]
        sec = h.get("sector") or "미분류"
        by_sector[sec] = by_sector.get(sec, 0) + h["eval_amount"]
    total = sum(by_type.values()) or 1
    fmt = lambda d_: [{"label": k, "eval_amount": v, "pct": round(v / total * 100, 2)}
                      for k, v in sorted(d_.items(), key=lambda x: -x[1])]
    return {"by_type": fmt(by_type), "by_sector": fmt(by_sector), "as_of": d["as_of"]}


def _nearest_value(rows: list, target_date) -> float | None:
    """target_date 이하 중 가장 가까운 값."""
    prev = [r for r in rows if r[0] <= target_date]
    return prev[-1][1] if prev else None


def get_period_returns() -> dict:
    """기간별 수익률 + 코스피 벤치마크·초과수익 (FR-03-24~25)."""
    from datetime import date, timedelta
    from backend.infra.schema import AssetSnapshot, MarketIndicator

    with get_session() as s:
        snaps = [(r.date, float(r.total_asset)) for r in
                 s.query(AssetSnapshot).order_by(AssetSnapshot.date).all()]
        kospi = [(r.date, r.value) for r in
                 s.query(MarketIndicator).filter_by(code="KOSPI")
                 .order_by(MarketIndicator.date).all()]
    if not snaps:
        return {"returns": [], "as_of": None}
    today = snaps[-1][0]
    cur = snaps[-1][1]
    cur_k = kospi[-1][1] if kospi else None

    out = []
    for label, days in (("1w", 7), ("1m", 30), ("3m", 90), ("1y", 365)):
        base = _nearest_value(snaps, today - timedelta(days=days))
        if base is None or base == 0:
            continue
        port = round((cur - base) / base * 100, 2)
        bench = None
        if cur_k and kospi:
            base_k = _nearest_value(kospi, today - timedelta(days=days))
            if base_k:
                bench = round((cur_k - base_k) / base_k * 100, 2)
        out.append({"period": label, "portfolio_pct": port, "benchmark_pct": bench,
                    "excess_pct": round(port - bench, 2) if bench is not None else None})
    return {"returns": out, "as_of": today.isoformat()}


def get_trend() -> list[dict]:
    """자산 추이 시계열 (FR-03-26)."""
    from backend.infra.schema import AssetSnapshot
    with get_session() as s:
        rows = s.query(AssetSnapshot).order_by(AssetSnapshot.date).all()
    return [{"date": r.date.isoformat(), "total_asset": float(r.total_asset),
             "total_eval": float(r.total_eval), "total_cash": float(r.total_cash)}
            for r in rows]


def reset_all() -> None:
    """전체 초기화 (D-020): 보유·예수금·계좌·파일 처리이력 삭제 — 재스캔으로 재적재."""
    from backend.infra.schema import CashBalance
    with get_session() as s:
        s.query(Holding).delete()
        s.query(CashBalance).delete()
        s.query(Account).delete()
        row = s.get(AppSetting, _PROCESSED_KEY)
        if row:
            s.delete(row)
        s.commit()
    logger.warning("포트폴리오 전체 초기화 완료")


# ── 화면 개선 (2026-07-14 시안 확정): 계좌별·분류별 뷰 ──

def get_by_account() -> dict:
    """계좌별 카드 데이터 — 종목·유효 예수금(수동 우선)·계좌 합계·비중."""
    from backend.infra.schema import CashBalance

    d = get_holdings()
    with get_session() as s:
        accounts = s.query(Account).all()
        cash_all = s.query(CashBalance).all()

    _rc = {}
    def _rate():
        if "v" not in _rc:
            _rc["v"] = _latest_usdkrw()
        return _rc["v"]

    holdings_by_acct: dict[str, list] = {}
    for h in d["holdings"]:
        holdings_by_acct.setdefault(h["account"], []).append(h)

    out = []
    for acc in accounts:
        hs = holdings_by_acct.get(acc.alias, [])
        rows = [c for c in cash_all if c.account_id == acc.id]
        cash, cash_source = _effective_cash(rows, _rate) if rows else (0.0, "file")
        ev = sum(h["eval_amount"] for h in hs)
        buy = sum(h["buy_amount"] for h in hs)
        pnl = sum(h["pnl_amount"] for h in hs)
        for h in hs:  # 계좌 내 비중
            h["weight_in_account_pct"] = round(h["eval_amount"] / ev * 100, 2) if ev else 0.0
        out.append({"name": acc.alias, "holdings": hs, "cash": round(cash, 2),
                    "cash_source": cash_source,
                    "eval_amount": ev, "buy_amount": buy, "pnl_amount": pnl,
                    "pnl_pct": round(pnl / buy * 100, 2) if buy else 0.0,
                    "total": round(ev + cash, 2)})
    grand = sum(a["total"] for a in out) or 1
    for a in out:
        a["weight_pct"] = round(a["total"] / grand * 100, 2)
    out.sort(key=lambda a: -a["total"])
    return {"accounts": out, "totals": d["totals"], "as_of": d["as_of"]}


GROUP_DIMS = {"invest", "sector"}

# 해외투자 국내 ETF 판별 키워드 (2026-07-14 사용자 정의)
_OVERSEAS_THEME_KEYWORDS = ("글로벌", "차이나", "미국", "금현물", "금채권")

INVEST_GROUP_ORDER = ["국내 개별주식", "해외 개별주식·ETF",
                      "해외투자 국내 ETF", "국내투자 국내 ETF"]


def _classify_invest(h) -> str:
    """투자유형 4분류: ①국내 개별 ②해외(전부) ③해외투자 국내ETF ④국내투자 국내ETF."""
    if h["market"] != "KRX":
        return "해외 개별주식·ETF"
    t = _classify_type(h["name"], h["market"])
    if "ETF" not in t:
        return "국내 개별주식"
    if any(k in h["name"] for k in _OVERSEAS_THEME_KEYWORDS):
        return "해외투자 국내 ETF"
    return "국내투자 국내 ETF"


def get_grouped(by: str) -> dict:
    """분류별 뷰 (FR-03-22~23): type=주식·ETF / region=국내·해외 / sector=산업."""
    if by not in GROUP_DIMS:
        raise ValueError(f"by는 {GROUP_DIMS} 중 하나여야 합니다")
    d = get_holdings()

    def label_of(h) -> str:
        if by == "invest":
            return _classify_invest(h)
        return h.get("sector") or "미분류"

    groups: dict[str, dict] = {}
    for h in d["holdings"]:
        g = groups.setdefault(label_of(h), {"holdings": [], "eval_amount": 0.0,
                                            "buy_amount": 0.0, "pnl_amount": 0.0})
        g["holdings"].append(h)
        g["eval_amount"] += h["eval_amount"]
        g["buy_amount"] += h["buy_amount"]
        g["pnl_amount"] += h["pnl_amount"]

    total_eval = sum(g["eval_amount"] for g in groups.values()) or 1
    out = []
    for label, g in groups.items():
        g["holdings"].sort(key=lambda x: -x["eval_amount"])
        out.append({"label": label, **g,
                    "pnl_pct": round(g["pnl_amount"] / g["buy_amount"] * 100, 2)
                               if g["buy_amount"] else 0.0,
                    "weight_pct": round(g["eval_amount"] / total_eval * 100, 2),
                    "count": len(g["holdings"]),
                    "account_count": len({h["account"] for h in g["holdings"]})})
    if by == "invest":  # 사용자 정의 고정 순서
        out.sort(key=lambda x: INVEST_GROUP_ORDER.index(x["label"])
                 if x["label"] in INVEST_GROUP_ORDER else 99)
    else:
        out.sort(key=lambda x: -x["eval_amount"])
    return {"by": by, "groups": out, "totals": d["totals"], "as_of": d["as_of"]}
