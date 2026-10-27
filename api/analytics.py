"""
Price Pulse Lahore — ML Analytics API
Statistical ML: Z-score anomalies, moving averages, day-of-week patterns,
inflation index, and 7-day linear forecast.
QA Pulse by SK · skakarh.com
"""

import math
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics & ML"])
limiter = Limiter(key_func=get_remote_address)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _query(sql: str, params: dict = None):
    try:
        from db.database import get_db
        from sqlalchemy import text
        with get_db() as db:
            result = db.execute(text(sql), params or {})
            return result.fetchall()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB query failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {e}")


def _stdev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


# ── /analytics/anomalies ───────────────────────────────────────────────────────

@router.get("/anomalies")
async def get_anomalies(
    request: Request,
    days: int = Query(30, ge=7, le=90, description="Lookback window for Z-score baseline"),
    z_threshold: float = Query(2.0, ge=1.0, le=4.0, description="Z-score threshold"),
):
    """
    Z-score anomaly detection.
    Flags items whose price today deviates > z_threshold std deviations
    from their mean over the last `days` days.
    """

    # Today's prices
    # Use most recent available date (pipeline may not have run today yet)
    latest_date_row = _query("SELECT MAX(CAST(date AS DATE)) FROM price_readings")
    latest_date = latest_date_row[0][0] if latest_date_row and latest_date_row[0][0] else None
    if not latest_date:
        raise HTTPException(status_code=404, detail="No data available yet")

    today_rows = _query("""
        SELECT i.slug, i.name_english, i.name_urdu, i.category, i.unit,
               r.avg_price, r.min_price, r.max_price, r.price_change_pct, r.direction,
               CAST(r.date AS DATE) as d
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE CAST(r.date AS DATE) = CAST(:latest AS DATE)
    """, {"latest": str(latest_date)})

    if not today_rows:
        raise HTTPException(status_code=404, detail="No data for latest date")

    # Historical prices per item (last N days, excluding latest date)
    history_rows = _query("""
        SELECT i.slug, r.avg_price, CAST(r.date AS DATE) as d
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE CAST(r.date AS DATE) >= CAST(:latest AS DATE) - INTERVAL '1 day' * :days
          AND CAST(r.date AS DATE) < CAST(:latest AS DATE)
        ORDER BY i.slug, d
    """, {"days": days, "latest": str(latest_date)})

    # Build per-item history map
    history_map = defaultdict(list)
    for row in history_rows:
        history_map[row[0]].append(float(row[1]))

    anomalies = []
    for row in today_rows:
        slug, name_en, name_ur, cat, unit, avg, min_p, max_p, chg_pct, direction, d = row
        hist = history_map.get(slug, [])
        if len(hist) < 5:
            continue  # not enough history

        mean  = _mean(hist)
        stdev = _stdev(hist)
        if stdev == 0:
            continue

        z = (float(avg) - mean) / stdev
        if abs(z) >= z_threshold:
            anomalies.append({
                "slug":             slug,
                "name_english":     name_en,
                "name_urdu":        name_ur or "",
                "category":         cat,
                "unit":             unit,
                "today_price":      float(avg),
                "historical_mean":  round(mean, 2),
                "historical_stdev": round(stdev, 2),
                "z_score":          round(z, 2),
                "price_change_pct": float(chg_pct) if chg_pct else None,
                "direction":        {"up":"rising","down":"falling"}.get(direction or "stable", direction or "stable"),
                "severity":         "high" if abs(z) >= 3 else "medium",
                "signal":           "spike" if z > 0 else "drop",
                "data_points":      len(hist),
            })

    anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    return {
        "date":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "lookback_days": days,
        "z_threshold": z_threshold,
        "count":       len(anomalies),
        "anomalies":   anomalies,
        "ml_status":   "z_score",
    }


# ── /analytics/trends/{slug} ───────────────────────────────────────────────────

@router.get("/trends/{slug}")
async def get_trends(
    request: Request,
    slug: str,
    days: int = Query(30, ge=7, le=150, description="Days of history"),
):
    """
    7-day moving average + direction trend for one item.
    """

    rows = _query("""
        SELECT CAST(r.date AS DATE) as d, r.avg_price, r.min_price, r.max_price,
               r.price_change_pct, r.direction
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE i.slug = :slug
          AND CAST(r.date AS DATE) >= CURRENT_DATE - INTERVAL '1 day' * :days
        ORDER BY d ASC
    """, {"slug": slug, "days": days})

    if not rows:
        raise HTTPException(status_code=404, detail=f"Item '{slug}' not found or no history")

    # Name lookup
    name_row = _query("""
        SELECT name_english, name_urdu, category, unit FROM items WHERE slug = :slug
    """, {"slug": slug})
    name_en = name_row[0][0] if name_row else slug
    name_ur = name_row[0][1] if name_row else ""
    category = name_row[0][2] if name_row else ""
    unit     = name_row[0][3] if name_row else ""

    prices = [float(r[1]) for r in rows]
    dates  = [str(r[0]) for r in rows]

    # 7-day moving average
    ma7 = []
    for i, p in enumerate(prices):
        window = prices[max(0, i - 6):i + 1]
        ma7.append(round(_mean(window), 2))

    # Trend direction (last 7 days slope)
    recent = prices[-7:]
    if len(recent) >= 2:
        slope = (recent[-1] - recent[0]) / len(recent)
        trend = "rising" if slope > 1 else "falling" if slope < -1 else "stable"
    else:
        trend = "stable"

    # Build series
    series = []
    for i, row in enumerate(rows):
        series.append({
            "date":             str(row[0]),
            "avg_price":        float(row[1]),
            "min_price":        int(row[2]) if row[2] else None,
            "max_price":        int(row[3]) if row[3] else None,
            "ma7":              ma7[i],
            "price_change_pct": float(row[4]) if row[4] else None,
            "direction":        row[5] or "stable",
        })

    # 7-day simple forecast (linear extrapolation)
    if len(prices) >= 7:
        avg_daily = (prices[-1] - prices[-7]) / 7
    elif len(prices) >= 2:
        avg_daily = (prices[-1] - prices[0]) / len(prices)
    else:
        avg_daily = 0

    forecast = []
    last_price = prices[-1]
    for i in range(1, 8):
        pred = round(max(0, last_price + avg_daily * i), 2)
        margin = round(pred * 0.04 * i, 2)
        forecast.append({
            "date":      (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d"),
            "predicted": pred,
            "lower":     round(max(0, pred - margin), 2),
            "upper":     round(pred + margin, 2),
        })

    return {
        "slug":         slug,
        "name_english": name_en,
        "name_urdu":    name_ur or "",
        "category":     category,
        "unit":         unit,
        "days":         days,
        "data_points":  len(series),
        "current_price": prices[-1] if prices else None,
        "trend":        trend,
        "series":       series,
        "forecast_7d":  forecast,
        "ml_status":    "moving_average_linear_forecast",
    }


# ── /analytics/dow-patterns ───────────────────────────────────────────────────

@router.get("/dow-patterns")
async def get_dow_patterns(
    request: Request,
    category: str = Query(None, description="Filter by category"),
    min_samples: int = Query(3, ge=2, description="Minimum samples per day-of-week to include"),
):
    """
    Day-of-week price patterns.
    Shows which weekdays have historically higher/lower prices per category.
    """

    sql = """
        SELECT i.category, i.name_english, i.slug,
               EXTRACT(DOW FROM r.date) as dow,
               AVG(r.avg_price) as avg_price,
               COUNT(*) as samples
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE CAST(r.date AS DATE) >= CURRENT_DATE - INTERVAL '150 days'
    """
    params = {}
    if category:
        sql += " AND i.category = :category"
        params["category"] = category
    sql += " GROUP BY i.category, i.name_english, i.slug, dow HAVING COUNT(*) >= :min_s ORDER BY i.category, i.slug, dow"
    params["min_s"] = min_samples

    rows = _query(sql, params)

    # Pivot: category → item → dow → avg_price
    DOW_NAMES = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

    by_category = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        cat, name, slug, dow, avg, samples = row
        by_category[cat][slug]["name_english"] = name
        by_category[cat][slug]["slug"] = slug
        by_category[cat][slug].setdefault("days", {})[int(dow)] = {
            "avg_price": round(float(avg), 2),
            "samples":   int(samples),
        }

    # Find cheapest/most expensive day per item
    result = []
    for cat, items in by_category.items():
        cat_items = []
        for slug, info in items.items():
            days = info.get("days", {})
            if not days:
                continue
            cheapest = min(days.items(), key=lambda x: x[1]["avg_price"])
            priciest = max(days.items(), key=lambda x: x[1]["avg_price"])
            variation = round(
                (priciest[1]["avg_price"] - cheapest[1]["avg_price"]) /
                cheapest[1]["avg_price"] * 100, 2
            ) if cheapest[1]["avg_price"] > 0 else 0

            cat_items.append({
                "slug":         slug,
                "name_english": info["name_english"],
                "cheapest_day": DOW_NAMES[cheapest[0]],
                "priciest_day": DOW_NAMES[priciest[0]],
                "variation_pct": variation,
                "by_day": {
                    DOW_NAMES[d]: v for d, v in sorted(days.items())
                },
            })

        cat_items.sort(key=lambda x: x["variation_pct"], reverse=True)
        result.append({"category": cat, "items": cat_items})

    return {
        "lookback_days": 150,
        "min_samples":   min_samples,
        "categories":    result,
        "ml_status":     "day_of_week_aggregation",
    }


# ── /analytics/summary ────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(request: Request):
    """
    Full market summary: today's movers, anomalies count, category signals,
    and inflation index vs 30 days ago.
    """

    # Today
    latest_date_row = _query("SELECT MAX(CAST(date AS DATE)) FROM price_readings")
    latest_date = latest_date_row[0][0] if latest_date_row and latest_date_row[0][0] else None
    if not latest_date:
        raise HTTPException(status_code=404, detail="No data available yet")

    today_rows = _query("""
        SELECT i.name_english, i.name_urdu, i.category, i.unit,
               r.avg_price, r.price_change_pct, r.direction
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE CAST(r.date AS DATE) = CAST(:latest AS DATE)
        ORDER BY r.price_change_pct DESC NULLS LAST
    """, {"latest": str(latest_date)})

    if not today_rows:
        raise HTTPException(status_code=404, detail="No data for latest date")

    # 30-day baseline avg per category
    baseline_rows = _query("""
        SELECT i.category, AVG(r.avg_price) as baseline
        FROM price_readings r
        JOIN items i ON r.item_id = i.id
        WHERE CAST(r.date AS DATE) BETWEEN CAST(:latest AS DATE) - INTERVAL '35 days'
                                       AND CAST(:latest AS DATE) - INTERVAL '5 days'
        GROUP BY i.category
    """, {"latest": str(latest_date)})
    baseline = {row[0]: float(row[1]) for row in baseline_rows}

    # Category stats
    cat_stats = defaultdict(lambda: {
        "item_count": 0, "avg_price": 0,
        "rising": 0, "falling": 0, "stable": 0,
        "total_change": 0, "change_count": 0,
    })
    top_gainers, top_losers = [], []

    for row in today_rows:
        name_en, name_ur, cat, unit, avg, chg_pct, direction = row
        s = cat_stats[cat]
        s["item_count"] += 1
        s["avg_price"]  += float(avg or 0)
        dir_key = {"up": "rising", "down": "falling"}.get(direction or "stable", direction or "stable")
        s[dir_key] += 1
        if chg_pct is not None:
            s["total_change"]  += float(chg_pct)
            s["change_count"]  += 1
            item = {
                "name_english": name_en, "name_urdu": name_ur or "",
                "category": cat, "unit": unit,
                "avg_price": float(avg), "price_change_pct": float(chg_pct),
                "direction": direction or "stable",
            }
            if float(chg_pct) > 0:
                top_gainers.append(item)
            elif float(chg_pct) < 0:
                top_losers.append(item)

    top_gainers.sort(key=lambda x: x["price_change_pct"], reverse=True)
    top_losers.sort(key=lambda x: x["price_change_pct"])

    categories = []
    for cat, s in cat_stats.items():
        avg_chg = round(s["total_change"] / s["change_count"], 2) if s["change_count"] else 0
        avg_p   = round(s["avg_price"] / s["item_count"], 2) if s["item_count"] else 0
        base    = baseline.get(cat)
        vs_baseline = round((avg_p - base) / base * 100, 2) if base and base > 0 else None
        categories.append({
            "category":        cat,
            "item_count":      s["item_count"],
            "avg_price":       avg_p,
            "avg_change_pct":  avg_chg,
            "vs_30d_baseline": vs_baseline,
            "rising":          s["rising"],
            "falling":         s["falling"],
            "stable":          s["stable"],
            "signal": "inflationary" if avg_chg > 3 else "deflationary" if avg_chg < -3 else "stable",
        })

    all_changes = [float(r[5]) for r in today_rows if r[5] is not None]
    overall_chg = round(_mean(all_changes), 2) if all_changes else 0

    return {
        "date":             datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_items":      len(today_rows),
        "overall_change_pct": overall_chg,
        "market_signal":    "inflationary" if overall_chg > 2 else "deflationary" if overall_chg < -2 else "stable",
        "categories":       categories,
        "top_gainers":      top_gainers[:5],
        "top_losers":       top_losers[:5],
        "ml_status":        "statistical_ml",
    }


# ── /analytics/inflation-index ────────────────────────────────────────────────

@router.get("/inflation-index")
async def get_inflation_index(
    request: Request,
    days: int = Query(90, ge=14, le=180),
):
    """
    Lahore market inflation index — daily average price level indexed to
    the first available day in the window.
    """

    rows = _query("""
        SELECT CAST(r.date AS DATE) as d, AVG(r.avg_price) as avg_p, COUNT(*) as n
        FROM price_readings r
        WHERE CAST(r.date AS DATE) >= CURRENT_DATE - INTERVAL '1 day' * :days
        GROUP BY d
        ORDER BY d ASC
    """, {"days": days})

    if not rows:
        raise HTTPException(status_code=404, detail="No historical data")

    series = [{"date": str(r[0]), "avg_price": round(float(r[1]), 2), "items": int(r[2])} for r in rows]
    baseline = series[0]["avg_price"]

    for s in series:
        s["index"] = round(s["avg_price"] / baseline * 100, 2) if baseline > 0 else 100.0

    current_index = series[-1]["index"] if series else 100.0
    change_vs_baseline = round(current_index - 100.0, 2)

    return {
        "baseline_date":      series[0]["date"] if series else None,
        "current_date":       series[-1]["date"] if series else None,
        "baseline_price":     baseline,
        "current_index":      current_index,
        "change_vs_baseline": change_vs_baseline,
        "signal":             "inflationary" if change_vs_baseline > 5 else "deflationary" if change_vs_baseline < -5 else "stable",
        "days":               days,
        "series":             series,
        "ml_status":          "price_index",
    }
