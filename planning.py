from __future__ import annotations

import pandas as pd

def fmt_num(value: object, digits: int = 2) -> str:
    try:
        if value is None or pd.isna(value):
            return "不确定"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "不确定"


def fmt_signed_pct(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "不确定"
        val = float(value)
        return f"{val:+.2f}%"
    except Exception:
        return "不确定"


def trade_plan(row: pd.Series) -> dict:
    code = str(row["code"]).zfill(6)
    price = float(row.get("hist_close", row.get("price")))
    ma5 = float(row["ma5"])
    ma10 = float(row["ma10"])
    ma20 = float(row["ma20"])
    ma60 = float(row["ma60"])
    ret20 = float(row["ret20"])
    ret60 = float(row["ret60"])
    pct_chg = float(row.get("pct_chg", 0) or 0)
    atr = float(row["atr14_pct"]) / 100 * price

    anchor = (ma5 + ma10) / 2
    short_low = anchor - 0.45 * atr
    short_high = anchor + 0.35 * atr
    if price <= short_high * 1.015:
        short_high = min(price * 1.01, short_high)
    short_stop = short_low - 0.85 * atr
    short_tp1 = short_high + 1.15 * atr
    short_tp2 = short_high + 2.15 * atr

    hot = pct_chg >= 9.5 or ret20 > 45 or ret60 > 120
    if hot:
        long_high = min(ma20 * 1.03, price * 0.88)
        long_low = max(ma60 * 1.02, price * 0.72)
        if long_low > long_high:
            long_low = min(ma20 * 0.92, long_high * 0.92)
    else:
        long_high = min(ma20 * 1.04, price * 0.94)
        long_low = max(ma60 * 1.02, ma20 * 0.90, price * 0.78)
        if long_low > long_high:
            long_low = long_high * 0.90
    long_stop = long_low - 1.6 * atr
    long_tp1 = long_high * 1.25
    long_tp2 = long_high * 1.45

    drivers = [
        f"报告期营收{fmt_signed_pct(row.get('rev_yoy'))}、净利{fmt_signed_pct(row.get('np_yoy'))}",
        f"20/60日涨幅 {fmt_num(ret20)}% / {fmt_num(ret60)}%",
    ]
    if pd.notna(row.get("main_net_ratio")):
        drivers.append(f"主力净占比 {fmt_num(row.get('main_net_ratio'))}%")
    if hot:
        drivers[-1] = "短线过热，等待回踩换手"

    return {
        "rank": 0,
        "code": code,
        "name": str(row["name"]),
        "score": round(float(row["score"]), 2),
        "price": round(price, 2),
        "change": round(pct_chg, 2),
        "action": "不追高" if hot else "等回踩",
        "hot": bool(hot),
        "shortBuy": f"{short_low:.2f}-{short_high:.2f}",
        "shortStop": f"{short_stop:.2f}",
        "shortTake": f"{short_tp1:.2f} / {short_tp2:.2f}",
        "longBuy": f"{long_low:.2f}-{long_high:.2f}",
        "longStop": f"{long_stop:.2f}",
        "longTake": f"{long_tp1:.2f} / {long_tp2:.2f}",
        "drivers": drivers[:3],
    }
