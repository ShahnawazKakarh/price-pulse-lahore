"""
Price Pulse Lahore — ML & Analytics API endpoints
Rule-based now, ML-powered later as data grows.
QA Pulse by SK · skakarh.com
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/analytics", tags=["Analytics & ML"])
limiter = Limiter(key_func=get_remote_address)


def load_data():
    """Load today's price data."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from db.database import check_connection, get_db
        from db.crud import get_today_prices
        if check_connection():
            with get_db() as db:
                return get_today_prices(db)
    except Exception:
        pass
    # JSON fallback
    import json
    daily_dir = Path(__file__).parent.parent / "data" / "daily"
    files = sorted(daily_dir.glob("*.json"), reverse=True) if daily_dir.exists() else []
    if files:
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)
    return []


def load_history(days: int = 30):
    """Load historical price data from multiple JSON files."""
    import json
    from pathlib import Path
    daily_dir = Path(__file__).parent.parent / "data" / "daily"
    if not daily_dir.exists():
        return []
    files = sorted(daily_dir.glob("*.json"), reverse=True)[:days]
    all_records = []
    for f in files:
        with open(f, encoding="utf-8") as fp:
            records = json.load(fp)
            all_records.extend(records)
    return all_records


@router.get("/summary")
async def get_summary(request: Request):
    """
    Daily market summary with inflation index per category.
    Phase 1: rule-based. Phase 2: ML-powered trend detection.
    """
    records = load_data()
    if not records:
        raise HTTPException(status_code=404, detail="No data available")

    summary = {}
    for r in records:
        cat = r.get("category", "unknown")
        if cat not in summary:
            summary[cat] = {
                "category":      cat,
                "item_count":    0,
                "avg_price":     0,
                "rising":        0,
                "falling":       0,
                "stable":        0,
                "avg_change_pct": 0,
                "change_count":  0,
            }
        s = summary[cat]
        s["item_count"]  += 1
        s["avg_price"]   += r.get("avg_price", (r.get("min_price",0) + r.get("max_price",0)) / 2)
        dir_ = r.get("direction", "stable")
        s[dir_] = s.get(dir_, 0) + 1
        if r.get("price_change_pct") is not None:
            s["avg_change_pct"] += r["price_change_pct"]
            s["change_count"]   += 1

    result = []
    for cat, s in summary.items():
        if s["item_count"] > 0:
            s["avg_price"]     = round(s["avg_price"] / s["item_count"], 2)
        if s["change_count"] > 0:
            s["avg_change_pct"] = round(s["avg_change_pct"] / s["change_count"], 2)
        del s["change_count"]
        # Inflation signal
        pct = s["avg_change_pct"]
        if pct > 3:     s["signal"] = "inflationary"
        elif pct < -3:  s["signal"] = "deflationary"
        else:           s["signal"] = "stable"
        result.append(s)

    # Overall market signal
    all_changes = [r.get("price_change_pct") for r in records if r.get("price_change_pct") is not None]
    overall_change = round(sum(all_changes) / len(all_changes), 2) if all_changes else 0

    return {
        "date":           records[0].get("date") if records else None,
        "overall_change_pct": overall_change,
        "market_signal":  "inflationary" if overall_change > 2 else "deflationary" if overall_change < -2 else "stable",
        "categories":     result,
        "ml_status":      "rule_based",
        "ml_note":        "ML forecasting available after 90 days of data collection",
    }


@router.get("/anomalies")
async def get_anomalies(request: Request, threshold: float = Query(10.0, description="% change threshold to flag as anomaly")):
    """
    Detect unusual price movements.
    Phase 1: threshold-based. Phase 2: statistical Z-score anomaly detection.
    """
    records = load_data()
    anomalies = []
    for r in records:
        pct = r.get("price_change_pct")
        if pct is not None and abs(pct) >= threshold:
            anomalies.append({
                "name_english":     r.get("name_english"),
                "name_urdu":        r.get("name_urdu", ""),
                "category":         r.get("category"),
                "avg_price":        r.get("avg_price"),
                "price_change_pct": pct,
                "direction":        r.get("direction"),
                "severity":         "high" if abs(pct) >= 20 else "medium",
                "unit":             r.get("unit"),
            })

    anomalies.sort(key=lambda x: abs(x["price_change_pct"]), reverse=True)

    return {
        "date":       records[0].get("date") if records else None,
        "threshold":  threshold,
        "count":      len(anomalies),
        "anomalies":  anomalies,
        "ml_status":  "threshold_based",
        "ml_note":    "Z-score anomaly detection available after 30 days of data",
    }


@router.get("/forecast/{slug}")
async def get_forecast(request: Request, slug: str):
    """
    Price forecast for a single item.
    Phase 1: linear trend extrapolation from available data.
    Phase 2: Prophet/LSTM forecast with confidence intervals.
    """
    history = load_history(days=30)
    item_history = [r for r in history if r.get("name_english", "").lower().replace(" ", "-") == slug or r.get("slug") == slug]

    if not item_history:
        # Return today's price as baseline
        today = load_data()
        match = next((r for r in today if r.get("name_english","").lower().replace(" ","-") == slug), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Item '{slug}' not found")
        item_history = [match]

    # Sort by date
    item_history.sort(key=lambda x: x.get("date", ""))

    # Get prices
    prices = [r.get("avg_price", (r.get("min_price",0)+r.get("max_price",0))/2) for r in item_history]
    latest = prices[-1] if prices else 0
    name   = item_history[-1].get("name_english", slug)

    # Simple linear trend
    if len(prices) >= 2:
        avg_daily_change = (prices[-1] - prices[0]) / len(prices)
    elif item_history[-1].get("price_change_pct"):
        avg_daily_change = latest * item_history[-1]["price_change_pct"] / 100
    else:
        avg_daily_change = 0

    # 7-day forecast
    forecast = []
    for i in range(1, 8):
        date = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
        predicted = round(max(0, latest + avg_daily_change * i), 2)
        # Simple confidence band (widens over time)
        margin = round(predicted * 0.05 * i, 2)
        forecast.append({
            "date":       date,
            "predicted":  predicted,
            "lower":      round(predicted - margin, 2),
            "upper":      round(predicted + margin, 2),
            "confidence": max(0.5, 0.95 - i * 0.05),
        })

    return {
        "slug":          slug,
        "name_english":  name,
        "current_price": latest,
        "data_points":   len(prices),
        "forecast":      forecast,
        "ml_status":     "linear_extrapolation" if len(prices) >= 2 else "insufficient_data",
        "ml_note":       "Prophet/LSTM forecasting available after 90 days of data. Currently using linear trend.",
    }


@router.get("/inflation-index")
async def get_inflation_index(request: Request):
    """
    Lahore market inflation index.
    Tracks overall price level changes over time.
    """
    history = load_history(days=30)
    today   = load_data()

    if not today:
        raise HTTPException(status_code=404, detail="No data available")

    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for r in history:
        d = r.get("date")
        if d:
            by_date[d].append(r.get("avg_price", (r.get("min_price",0)+r.get("max_price",0))/2))

    # Compute daily average
    daily_avg = []
    for date in sorted(by_date.keys()):
        prices = by_date[date]
        daily_avg.append({"date": date, "avg_price": round(sum(prices)/len(prices), 2)})

    # Compute change vs first available day
    baseline = daily_avg[0]["avg_price"] if daily_avg else None
    for d in daily_avg:
        if baseline and baseline > 0:
            d["index"] = round((d["avg_price"] / baseline) * 100, 2)
        else:
            d["index"] = 100.0

    # Today's overall stats
    all_changes = [r.get("price_change_pct") for r in today if r.get("price_change_pct") is not None]
    today_change = round(sum(all_changes)/len(all_changes), 2) if all_changes else 0

    return {
        "date":          today[0].get("date") if today else None,
        "today_change":  today_change,
        "baseline_date": daily_avg[0]["date"] if daily_avg else None,
        "history":       daily_avg,
        "total_items":   len(today),
        "ml_status":     "statistical",
    }
