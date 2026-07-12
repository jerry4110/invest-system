"""투자저널 서비스 (M6, FR-06-01~06) — 실현손익(이동평균법)·판단근거·통계."""
import logging
from collections import defaultdict
from decimal import Decimal

from backend.adapters.broker.trades_file import parse_trades_file
from backend.infra.db import get_session
from backend.infra.schema import Transaction

logger = logging.getLogger(__name__)


def import_trades_file(path, account_alias: str = "미래에셋(파일)") -> int:
    """거래내역 임포트 (중복 제외) 후 실현손익 전체 재계산."""
    from backend.services.portfolio_service import _get_or_create_account

    trades = parse_trades_file(path)
    account_id = _get_or_create_account(account_alias)
    imported = 0
    with get_session() as s:
        for t in trades:
            dup = (s.query(Transaction)
                   .filter_by(account_id=account_id, ticker=t.ticker, side=t.side,
                              executed_at=t.executed_at)
                   .filter(Transaction.qty == t.qty, Transaction.price == t.price)
                   .first())
            if dup:
                continue
            s.add(Transaction(account_id=account_id, ticker=t.ticker, side=t.side,
                              qty=t.qty, price=t.price, executed_at=t.executed_at,
                              note=f"수수료:{t.fee}" if t.fee else ""))
            imported += 1
        s.commit()
    recompute_realized_pnl()
    return imported


def recompute_realized_pnl() -> None:
    """이동평균법 (FR-06-02): 종목별 시간순 — 매수는 평단 갱신, 매도는 실현손익.

    금액 계산은 Decimal (constitution §2.4). 수수료는 note의 '수수료:' 값을 차감.
    보유 원가 불명 상태의 매도(초과 매도)는 계산 보류(None) — 데이터 불일치 격리.
    """
    with get_session() as s:
        txs = s.query(Transaction).order_by(Transaction.executed_at, Transaction.id).all()
        pos: dict[str, dict] = defaultdict(lambda: {"qty": Decimal(0), "avg": Decimal(0)})
        for t in txs:
            fee = Decimal(t.note.split("수수료:")[1]) if "수수료:" in (t.note or "") else Decimal(0)
            qty, price = Decimal(str(t.qty)), Decimal(str(t.price))
            p = pos[t.ticker]
            if t.side == "buy":
                total_cost = p["avg"] * p["qty"] + price * qty
                p["qty"] += qty
                p["avg"] = total_cost / p["qty"] if p["qty"] else Decimal(0)
                t.realized_pnl = None
            else:
                if p["qty"] < qty:
                    logger.warning("초과 매도 감지(원가 불명): %s %s주 — 실현손익 보류",
                                   t.ticker, qty)
                    t.realized_pnl = None
                else:
                    t.realized_pnl = float((price - p["avg"]) * qty - fee)
                    p["qty"] -= qty
        s.commit()


def list_transactions() -> list[dict]:
    with get_session() as s:
        txs = s.query(Transaction).order_by(Transaction.executed_at.desc()).all()
    return [{
        "id": t.id, "ticker": t.ticker, "side": t.side, "qty": float(t.qty),
        "price": float(t.price), "executed_at": t.executed_at.isoformat(timespec="seconds"),
        "realized_pnl": t.realized_pnl,
        "note": (t.note or "").split("수수료:")[0].strip() or
                ("" if "수수료:" not in (t.note or "") else ""),
    } for t in txs]


def set_note(tx_id: int, note: str) -> None:
    """FR-06-03: 판단 근거 기록 (수수료 메타는 보존)."""
    with get_session() as s:
        t = s.get(Transaction, tx_id)
        fee_part = ""
        if "수수료:" in (t.note or ""):
            fee_part = " 수수료:" + t.note.split("수수료:")[1]
        t.note = note + fee_part
        s.commit()


def get_stats() -> dict:
    """FR-06-05: 승률·손익비·월별 실현손익."""
    with get_session() as s:
        sells = (s.query(Transaction)
                 .filter(Transaction.side == "sell", Transaction.realized_pnl.isnot(None))
                 .all())
    wins = [t.realized_pnl for t in sells if t.realized_pnl > 0]
    losses = [-t.realized_pnl for t in sells if t.realized_pnl < 0]
    monthly: dict[str, float] = defaultdict(float)
    for t in sells:
        monthly[t.executed_at.strftime("%Y-%m")] += t.realized_pnl
    return {
        "sell_count": len(sells),
        "total_realized_pnl": round(sum(t.realized_pnl for t in sells), 2),
        "win_rate_pct": round(len(wins) / len(sells) * 100, 1) if sells else 0.0,
        "payoff_ratio": round((sum(wins) / len(wins)) / (sum(losses) / len(losses)), 4)
                        if wins and losses else None,
        "monthly": [{"month": m, "realized_pnl": round(v, 2)}
                    for m, v in sorted(monthly.items())],
    }
