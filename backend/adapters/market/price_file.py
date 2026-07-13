"""백테스트용 가격 파일 파서 (FR-07-01) — 날짜·가격 컬럼 자동 감지."""
from datetime import date
from pathlib import Path

import pandas as pd

from backend.adapters.broker.file_upload import ParseError, _clean_number, _read_raw

DATE_HEADERS = ("일자", "날짜", "date", "Date", "거래일")
PRICE_HEADERS = ("종가", "지수", "가격", "close", "Close", "현재가")


def parse_price_file(path: str | Path) -> tuple[list[date], list[float]]:
    df = _read_raw(Path(path))
    header_row, d_col, p_col = None, None, None
    for i in range(min(len(df), 20)):
        row = [str(c).strip() if not pd.isna(c) else "" for c in df.iloc[i]]
        d = next((j for j, c in enumerate(row) if c in DATE_HEADERS), None)
        p = next((j for j, c in enumerate(row) if c in PRICE_HEADERS), None)
        if d is not None and p is not None:
            header_row, d_col, p_col = i, d, p
            break
    if header_row is None:
        raise ParseError("가격 파일에서 날짜·가격 컬럼(일자/종가 등)을 찾지 못했습니다")

    dates, values = [], []
    for _, row in df.iloc[header_row + 1:].iterrows():
        raw_d, raw_p = row.iloc[d_col], row.iloc[p_col]
        if pd.isna(raw_d) or pd.isna(raw_p):
            continue
        try:
            d = pd.to_datetime(str(raw_d)).date()
            v = float(_clean_number(raw_p))
        except (ValueError, ParseError):
            continue
        dates.append(d)
        values.append(v)
    if len(values) < 2:
        raise ParseError("가격 데이터가 2개 미만입니다 — 파일 내용을 확인하세요")
    pairs = sorted(zip(dates, values))
    return [p[0] for p in pairs], [p[1] for p in pairs]
