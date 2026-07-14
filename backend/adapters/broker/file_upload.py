"""파일 기반 계좌 연동 어댑터 (D-013) — 잔고 엑셀/CSV 파싱.

- 헤더 행 자동 감지 (상단 잡음 행 허용)
- 표준 헤더 후보 + 사용자 컬럼 매핑 오버라이드 (FR-03-01, 04)
- 천단위 콤마·통화기호 정제, Decimal 변환
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from backend.adapters.broker.base import HoldingDTO


class ParseError(Exception):
    """파싱 실패 — 사용자에게 컬럼 매핑 안내가 필요한 경우."""


# 표준 필드 → 헤더 후보 (미래에셋 HTS/홈페이지 및 일반 증권사 잔고 양식)
HEADER_CANDIDATES: dict[str, list[str]] = {
    "name":        ["종목명", "종목", "상품명", "이름"],
    "ticker":      ["종목코드", "종목번호", "코드", "티커"],
    "qty":         ["보유수량", "잔고수량", "수량", "보유주식수", "잔고", "보유량"],
    "avg_price":   ["매입평균가", "평균단가", "매입단가", "평단가", "평균매입가"],
    "buy_amount":  ["매입금액", "매수금액", "투자금액", "매입원금"],
    "cur_price":   ["현재가", "현재가격", "시세", "종가"],
    "eval_amount": ["평가금액", "평가액", "잔고평가금액"],
    "pnl_amount":  ["평가손익", "손익", "평가손익금액", "손익금액"],
    "pnl_pct":     ["수익률", "수익률(%)", "손익률", "수익율"],
    "region":      ["지역", "시장", "국가", "시장구분"],
    "sector":      ["카테고리", "산업", "섹터", "업종"],
    "asset_type":  ["유형", "자산유형", "상품유형"],
}
REQUIRED = {"name", "qty"}  # 최소 필수 — 나머지는 계산으로 보완


def _clean_number(v) -> Decimal:
    if pd.isna(v):
        return Decimal("0")
    s = (str(v).replace(",", "").replace("원", "").replace("₩", "")
         .replace("$", "").replace("%", "").strip())
    if s in ("", "-"):
        return Decimal("0")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ParseError(f"숫자 변환 실패: {v!r}") from e


def _read_raw(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, header=None, dtype=str)
    try:
        return pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig",
                           skip_blank_lines=False)
    except UnicodeDecodeError:
        # 미래에셋 내보내기 기본 인코딩 cp949 (2026-07-13 실파일 확인)
        return pd.read_csv(path, header=None, dtype=str, encoding="cp949",
                           skip_blank_lines=False)
    except pd.errors.ParserError:
        # 행마다 필드 수가 다른 경우 — csv 모듈로 직접 읽어 최대 폭 기준 정렬
        import csv
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        width = max((len(r) for r in rows), default=0)
        padded = [r + [None] * (width - len(r)) for r in rows]
        return pd.DataFrame(padded, dtype=str)


def _find_header_row(df: pd.DataFrame, mapping: dict[str, str] | None) -> tuple[int, dict[str, int]]:
    """알려진 헤더가 3개 이상 등장하는 첫 행을 헤더로 판정."""
    candidates = ({f: [h] for f, h in mapping.items()} if mapping else HEADER_CANDIDATES)
    for i in range(min(len(df), 20)):
        row = [str(c).strip() if not pd.isna(c) else "" for c in df.iloc[i]]
        col_idx: dict[str, int] = {}
        for field, names in candidates.items():
            for j, cell in enumerate(row):
                if cell in names:
                    col_idx[field] = j
                    break
        if len(col_idx) >= 3 and REQUIRED <= set(col_idx):
            return i, col_idx
    raise ParseError(
        "잔고 파일에서 인식 가능한 컬럼을 찾지 못했습니다. "
        "설정 > 컬럼 매핑에서 파일의 실제 헤더명을 지정해 주세요. "
        f"(필수: 종목명·보유수량 / 인식 후보 예: {', '.join(HEADER_CANDIDATES['qty'])})")


CASH_TYPES = ("통화", "원화RP", "RP", "예수금", "현금")
CASH_NAME_KEYWORDS = ("현금성자산", "CMA", "RP_")


def normalize_ticker(raw: str) -> str:
    """미래에셋 종목번호 정규화: A005930 → 005930."""
    t = raw.strip()
    if len(t) == 7 and t[0].upper() == "A" and t[1:].isalnum() and any(c.isdigit() for c in t[1:]):
        return t[1:]
    return t


def _classify_market(ticker: str, region: str) -> str:
    """상장시장 분류 — 한국 코드 패턴(6자리 영숫자, 숫자 포함) 우선, '지역' 컬럼은 보조.

    주의: 미래에셋 '지역' 컬럼은 기초자산 지역(예: 글로벌반도체 ETF=기타)이라
    상장시장 판별에 단독 사용 불가 (2026-07-12 실파일 검증).
    """
    if ticker.isdigit():
        return "KRX"
    if len(ticker) == 6 and ticker.isalnum() and any(c.isdigit() for c in ticker):
        return "KRX"   # 0091P0 같은 우선주·ETF 코드
    if region:
        return "KRX" if region == "국내" else "OVERSEAS"
    return "OVERSEAS" if ticker.isalpha() else "UNKNOWN"


TRADE_FILE_HEADERS = ("거래일자", "체결일자", "주문일자", "거래일", "매매구분")


def parse_balance_file(path: str | Path, mapping: dict[str, str] | None = None) -> list[HoldingDTO]:
    path = Path(path)
    df = _read_raw(path)

    # 거래내역 파일 오인 방지 (2026-07-13 실사용 버그): 잔고에는 거래일자류 헤더가 없다
    for i in range(min(len(df), 20)):
        cells = {str(c).strip() for c in df.iloc[i] if not pd.isna(c)}
        if cells & set(TRADE_FILE_HEADERS):
            raise ParseError(
                f"{path.name}: 거래내역 파일로 보입니다 — 잔고 폴더가 아닌 "
                "투자저널 페이지에서 업로드하세요")

    header_row, col_idx = _find_header_row(df, mapping)

    holdings: list[HoldingDTO] = []
    for _, row in df.iloc[header_row + 1:].iterrows():
        def get(field, default=""):
            j = col_idx.get(field)
            return row.iloc[j] if j is not None and j < len(row) else default

        name = str(get("name")).strip()
        if not name or pd.isna(get("name")) or name == "nan":
            continue  # 합계·빈 행 스킵
        qty = _clean_number(get("qty"))
        if qty == 0:
            continue
        asset_type = str(get("asset_type", "")).strip()
        is_cash_row = (asset_type in CASH_TYPES
                       or any(k in name for k in CASH_NAME_KEYWORDS))
        avg = _clean_number(get("avg_price"))
        buy = _clean_number(get("buy_amount")) or (qty * avg)
        if avg == 0 and qty:
            avg = buy / qty if buy else _clean_number(get("eval_amount")) / qty
        cur = _clean_number(get("cur_price"))
        ev = _clean_number(get("eval_amount")) or (qty * cur)
        pnl = _clean_number(get("pnl_amount")) or (ev - buy)
        # 수익률: 파일값은 %·비율 등 형식이 제각각 → 매입금액이 있으면 재계산이 진실
        if buy:
            pct = float(pnl / buy * 100)
        else:
            try:
                pct = float(_clean_number(get("pnl_pct")))
            except ParseError:
                pct = 0.0
        ticker = normalize_ticker(str(get("ticker", "")))
        region = str(get("region", "")).strip()
        if is_cash_row:
            market = "CASH_USD" if ticker.upper() == "USD" or "달러" in name else "CASH_KRW"
        elif asset_type == "해외주식":
            market = "OVERSEAS"
        elif asset_type == "주식":
            market = "KRX"
        else:
            market = _classify_market(ticker, region)
        holdings.append(HoldingDTO(name=name, ticker=ticker or name, qty=qty,
                                   avg_price=avg, buy_amount=buy, cur_price=cur,
                                   eval_amount=ev, pnl_amount=pnl, pnl_pct=pct,
                                   market=market,
                                   sector=(str(get("sector", "")).strip().replace("nan", "")
                                           or __import__("backend.adapters.broker.sector_map",
                                                         fromlist=["infer_sector"]).infer_sector(name)),
                                   currency="USD" if asset_type == "해외주식" else "KRW"))
    if not holdings:
        raise ParseError("파일에서 보유 종목을 찾지 못했습니다 — 컬럼 매핑을 확인해 주세요.")
    return holdings
