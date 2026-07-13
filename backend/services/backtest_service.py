"""백테스트 서비스 (M7-1) — 업로드 실행·시나리오 저장·차트 (FR-07-01~05)."""
import json
from datetime import datetime
from pathlib import Path

from backend.adapters.market.price_file import parse_price_file
from backend.domain.backtest import metrics_from_equity
from backend.infra.db import get_session
from backend.infra.schema import BacktestRun

DISCLAIMER = ("과거 성과는 미래 수익을 보장하지 않습니다. "
              "본 백테스트는 수수료·슬리피지·세금을 반영하지 않습니다.")


def run_buyhold_from_file(path: str | Path, name: str) -> dict:
    """업로드 데이터 매수후보유 성과 (FR-07-01·03)."""
    dates, values = parse_price_file(path)
    metrics = metrics_from_equity(dates, values)
    curve = _downsample(dates, values, 300)
    run_id = _save_run(name, "buyhold", {}, metrics, dates, values)
    return {"run_id": run_id, "name": name, "metrics": metrics, "curve": curve,
            "start": dates[0].isoformat(), "end": dates[-1].isoformat(),
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "disclaimer": DISCLAIMER}


def _downsample(dates, values, n: int) -> list[dict]:
    step = max(len(values) // n, 1)
    return [{"date": d.isoformat(), "value": round(v, 4)}
            for d, v in list(zip(dates, values))[::step]]


def _save_run(name, strategy, params, metrics, dates, values) -> int:
    with get_session() as s:
        run = BacktestRun(name=name, strategy=strategy,
                          params_json=json.dumps(params, ensure_ascii=False),
                          metrics_json=json.dumps(metrics, ensure_ascii=False),
                          curve_json=json.dumps(_downsample(dates, values, 500)),
                          created_at=datetime.now())
        s.add(run)
        s.commit()
        return run.id


def list_runs() -> list[dict]:
    with get_session() as s:
        rows = s.query(BacktestRun).order_by(BacktestRun.id.desc()).limit(30).all()
    return [{"id": r.id, "name": r.name, "strategy": r.strategy,
             "metrics": json.loads(r.metrics_json),
             "created_at": r.created_at.isoformat(timespec="seconds")} for r in rows]


def render_chart_png(run_id: int) -> bytes | None:
    """정적 시각화 (FR-07-04) — 자산곡선 + 드로다운."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with get_session() as s:
        run = s.get(BacktestRun, run_id)
    if not run:
        return None
    curve = json.loads(run.curve_json)
    values = [c["value"] for c in curve]
    peak, dd = values[0], []
    for v in values:
        peak = max(peak, v)
        dd.append((v - peak) / peak * 100)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    x = range(len(values))
    ax1.plot(x, values, color="#2563eb")
    ax1.set_title(f"{run.name} — equity curve")
    ax2.fill_between(x, dd, 0, color="#dc2626", alpha=0.4)
    ax2.set_ylabel("DD %")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    return buf.getvalue()
