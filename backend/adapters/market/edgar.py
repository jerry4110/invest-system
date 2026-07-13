"""SEC EDGAR 13F 어댑터 (M7-3, FR-07-21~23, D-017) — 공식 원천 직접 파싱."""
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)
_UA = {"User-Agent": "invest-system personal research jerry.kim@kido.co.kr"}
NS = "{http://www.sec.gov/edgar/document/thirteenf/informationtable}"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def parse_infotable(xml_bytes: bytes) -> list[dict]:
    """13F information table → 종목별 합산·비중 내림차순."""
    root = ET.fromstring(xml_bytes)
    agg: dict[str, dict] = {}
    for it in root.iter(f"{NS}infoTable"):
        issuer = (it.findtext(f"{NS}nameOfIssuer") or "").strip()
        cusip = (it.findtext(f"{NS}cusip") or "").strip()
        value = int(it.findtext(f"{NS}value") or 0)
        shares_el = it.find(f"{NS}shrsOrPrnAmt/{NS}sshPrnamt")
        shares = int(shares_el.text) if shares_el is not None and shares_el.text else 0
        key = cusip or issuer
        row = agg.setdefault(key, {"issuer": issuer, "cusip": cusip, "value": 0, "shares": 0})
        row["value"] += value
        row["shares"] += shares
    total = sum(r["value"] for r in agg.values()) or 1
    out = sorted(agg.values(), key=lambda r: -r["value"])
    for r in out:
        r["weight_pct"] = round(r["value"] / total * 100, 2)
    return out


def classify_changes(current: list[dict], previous: list[dict]) -> list[dict]:
    """분기 대비 변동: 신규/청산/확대/축소/유지 (FR-07-21)."""
    prev_by = {p["cusip"] or p["issuer"]: p for p in previous}
    cur_by = {c["cusip"] or c["issuer"]: c for c in current}
    changes = []
    for key, cur in cur_by.items():
        prev = prev_by.get(key)
        if prev is None:
            change, delta = "신규", None
        else:
            delta = cur["shares"] - prev["shares"]
            change = "확대" if delta > 0 else "축소" if delta < 0 else "유지"
        changes.append({"issuer": cur["issuer"], "change": change,
                        "shares": cur["shares"], "delta_shares": delta})
    for key, prev in prev_by.items():
        if key not in cur_by:
            changes.append({"issuer": prev["issuer"], "change": "청산",
                            "shares": 0, "delta_shares": -prev["shares"]})
    order = {"신규": 0, "확대": 1, "축소": 2, "청산": 3, "유지": 4}
    return sorted(changes, key=lambda c: order[c["change"]])


def fetch_two_filings(cik: str) -> tuple[dict, dict | None]:
    """최신·직전 13F-HR 공시 (information table XML 포함)."""
    cik10 = str(int(cik)).zfill(10)
    subs = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik10}.json"))
    recent = subs["filings"]["recent"]
    filings = [
        {"accession": recent["accessionNumber"][i], "period": recent["reportDate"][i]}
        for i, form in enumerate(recent["form"]) if form == "13F-HR"
    ][:2]
    if not filings:
        raise RuntimeError(f"CIK {cik}의 13F-HR 공시를 찾지 못했습니다")

    out = []
    for f in filings:
        acc = f["accession"].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
        index = json.loads(_get(f"{base}/index.json"))
        xml_name = next((it["name"] for it in index["directory"]["item"]
                         if it["name"].lower().endswith(".xml")
                         and "primary_doc" not in it["name"].lower()), None)
        if xml_name is None:
            raise RuntimeError("information table XML을 찾지 못했습니다")
        out.append({**f, "xml": _get(f"{base}/{xml_name}")})
    return out[0], (out[1] if len(out) > 1 else None)
