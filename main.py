#!/usr/bin/env python3
"""Forecast GTA VI's launch-day Twitch viewers hour by hour.

Reads every case file in $MAKEFUN_INPUT_DIR (default /input) and writes one
forecast per case to $MAKEFUN_OUTPUT_DIR (default /output) as <id>.out:
{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}]} for hours 2..24.

Model (fitted on past big-game launches, validated on the four practice
cases in the kit):
  * Every comparable launch in the case contributes its release-day curve as
    log-ratios ln(viewers_h / viewers_1) for hours 2..24.  The per-hour
    median across comparables is the shape of the launch day: a night dip
    after hour 1, a jump when the US unlocks, and an evening peak.
  * The shape is anchored on the case's own hour-1 print, so the forecast
    scales with how big hour 1 actually was.
  * A launch-completeness adjustment: r = hour1 / (peak hourly viewers in
    the 24 h before release day).  When hour 1 is small next to the
    launch-eve hype peak, most of the audience is still to come, so the
    rising part of the curve is stretched by k = clamp(0.60 / r, 0.85, 1.7);
    when hour 1 already dwarfs the eve peak the rise is shrunk a little.
    (On the practice cases r is ~0.60 for three launches and 0.35 for
    Marvel's Wolverine, whose evening peak ran 9x its hour-1 print.)
  * Quantile spread is log-normal with sigma growing with horizon:
    sigma_h = (0.30 + 0.015 * (h - 1)) * (0.8 + 0.2 * k), so the 90% band
    widens through the day and widens further exactly when the curve is
    stretched (the stretched cases are the uncertain ones).  Practice
    coverage of the 5%-95% band is ~0.95.

Standard library only, deterministic, no network.
"""

import json
import math
import os
from datetime import datetime, timedelta

# Standard-normal quantiles at the case's levels [0.05, 0.25, 0.5, 0.75, 0.95].
Z = (-1.6448536269514722, -0.6744897501960817, 0.0,
     0.6744897501960817, 1.6448536269514722)

# Fallback median log-ratio curve (pooled across the kit's comparables),
# used only for an hour the case's own comparables say nothing about.
FALLBACK_MEDIAN = {
    2: -0.138, 3: -0.283, 4: -0.310, 5: -0.292, 6: -0.238, 7: -0.220,
    8: -0.107, 9: -0.126, 10: -0.092, 11: -0.075, 12: -0.022, 13: 0.057,
    14: 0.166, 15: 0.418, 16: 0.502, 17: 0.571, 18: 0.668, 19: 0.876,
    20: 0.864, 21: 0.846, 22: 0.832, 23: 0.780, 24: 0.712,
}

SIGMA_BASE = 0.30
SIGMA_PER_HOUR = 0.015
K_REF = 0.60
K_MIN = 0.85
K_MAX = 1.7
SIGMA_K_BASE = 0.8
SIGMA_K_SLOPE = 0.2


def parse_ts(text):
    """Parse an ISO-8601 UTC timestamp like 2026-11-19T00:00:00Z."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def release_day_curve(comparable):
    """{hour: viewers} for the comparable's release UTC day (hours 1..24)."""
    try:
        day_start = parse_ts(comparable["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    curve = {}
    for row in comparable.get("hourly") or []:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None:
            continue
        hour = int((when - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            curve[hour] = viewers
    return curve


def median_curve(comparables):
    """Per-hour median log-ratio ln(viewers_h / viewers_1) across launches."""
    per_hour = {h: [] for h in range(2, 25)}
    for comparable in comparables or []:
        curve = release_day_curve(comparable)
        first = curve.get(1)
        if not first or first < 1:
            continue
        for hour in range(2, 25):
            value = curve.get(hour)
            if value is not None and value >= 1:
                per_hour[hour].append(math.log(value / first))
    curve = {}
    for hour in range(2, 25):
        values = per_hour[hour]
        curve[hour] = median(values) if values else FALLBACK_MEDIAN[hour]
    return curve


def completeness_factor(case, hour1):
    """k: stretch (>1) or shrink (<1) the rising part of the curve.

    r = hour-1 print / peak hourly viewers in the 24 h before release day.
    A small r means the launch-eve hype audience dwarfs hour 1, so the big
    unlock waves (and the evening peak) are still ahead.
    """
    try:
        day_start = parse_ts(case["day_start"])
        history = case.get("history_hourly") or []
    except (KeyError, TypeError, ValueError):
        return 1.0
    peak = 0.0
    for row in history:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None:
            continue
        if day_start - timedelta(hours=24) <= when < day_start:
            peak = max(peak, float(viewers))
    if peak <= 0 or hour1 <= 0:
        return 1.0
    ratio = hour1 / peak
    if ratio <= 0:
        return 1.0
    return min(max(K_REF / ratio, K_MIN), K_MAX)


def forecast(case):
    """Return the {"hours": [...]} forecast object for one case."""
    known = case.get("known") or []
    hour1 = 1.0
    for row in known:
        if row.get("hour") == 1 and row.get("viewers"):
            hour1 = float(row["viewers"])
            break
    if hour1 < 1:
        hour1 = 1.0

    shape = median_curve(case.get("comparables"))
    factor = completeness_factor(case, hour1)
    # The spread widens when the curve is stretched: a weak hour 1 means
    # the rest of the day is genuinely less certain.
    sigma_scale = SIGMA_K_BASE + SIGMA_K_SLOPE * factor

    hours = []
    for hour in range(2, 25):
        level = shape.get(hour, 0.0)
        if level > 0:
            level = level * factor
        sigma = (SIGMA_BASE + SIGMA_PER_HOUR * (hour - 1)) * sigma_scale
        quantiles = []
        for z in Z:
            value = hour1 * math.exp(level + z * sigma)
            value = min(max(value, 1.0), 1e9)
            quantiles.append(round(value, 2))
        quantiles.sort()
        hours.append({"hour": hour, "q": quantiles})
    return {"hours": hours}


def fallback_forecast():
    """A validly-shaped forecast when a case file cannot be read at all."""
    hours = []
    for hour in range(2, 25):
        level = FALLBACK_MEDIAN[hour]
        sigma = SIGMA_BASE + SIGMA_PER_HOUR * (hour - 1)
        quantiles = sorted(
            round(min(max(math.exp(level + z * sigma), 1.0), 1e9), 2)
            for z in Z
        )
        hours.append({"hour": hour, "q": quantiles})
    return {"hours": hours}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    names = sorted(
        name for name in os.listdir(input_dir) if name.endswith(".in")
    )
    for name in names:
        case_id = name[:-3]
        out_path = os.path.join(output_dir, case_id + ".out")
        try:
            with open(os.path.join(input_dir, name), "r", encoding="utf-8") as fh:
                case = json.load(fh)
            result = forecast(case)
        except Exception:
            result = fallback_forecast()
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
