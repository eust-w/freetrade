from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get("FREETRADE_DATA_DIR", str(ROOT / "var"))) / "outputs"
RUN_DATE = os.environ.get("RUN_DATE") or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
TODAY = RUN_DATE


def em_json(url: str, params: dict, retries: int = 4) -> dict:
    last_error: Exception | None = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=18)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data") is None and data.get("result") is None:
                raise RuntimeError(data.get("message") or "empty response")
            return data
        except Exception as exc:
            last_error = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"Eastmoney request failed: {last_error}")


def get_spot() -> pd.DataFrame:
    urls = [
        "https://82.push2.eastmoney.com/api/qt/clist/get",
        "https://push2.eastmoney.com/api/qt/clist/get",
        "https://50.push2.eastmoney.com/api/qt/clist/get",
    ]
    fields = ",".join(
        [
            "f12",
            "f13",
            "f14",
            "f2",
            "f3",
            "f4",
            "f5",
            "f6",
            "f7",
            "f8",
            "f9",
            "f10",
            "f11",
            "f15",
            "f16",
            "f17",
            "f18",
            "f20",
            "f21",
            "f22",
            "f23",
            "f24",
            "f25",
            "f62",
            "f184",
        ]
    )
    base_params = {
        "pz": 100,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048,m:1+t:81+s:2048",
        "fields": fields,
    }
    data = []
    total = None
    page = 1
    while total is None or len(data) < total:
        params = {**base_params, "pn": page}
        payload = None
        last_error = None
        for page_attempt in range(2):
            for url in urls:
                try:
                    payload = em_json(url, params, retries=3)["data"]
                    break
                except Exception as exc:
                    last_error = exc
            if payload is not None:
                break
            time.sleep(1.0 * (page_attempt + 1))
        if payload is None:
            raise RuntimeError(f"spot page {page} failed: {last_error}")
        total = int(payload["total"])
        rows = payload.get("diff") or []
        if not rows:
            raise RuntimeError("incomplete spot pagination")
        data.extend(rows)
        page += 1
        if page > 200:
            raise RuntimeError("spot pagination exceeded limit")
        time.sleep(0.15)
    if len({str(row["f12"]) for row in data}) != total:
        raise RuntimeError("spot pagination count mismatch or duplicate symbols")
    df = pd.DataFrame(data)
    rename = {
        "f12": "code",
        "f13": "market",
        "f14": "name",
        "f2": "price",
        "f3": "pct_chg",
        "f4": "chg",
        "f5": "volume",
        "f6": "amount",
        "f7": "amplitude",
        "f8": "turnover",
        "f9": "pe_dynamic",
        "f10": "volume_ratio",
        "f11": "five_min_chg",
        "f15": "high",
        "f16": "low",
        "f17": "open",
        "f18": "pre_close",
        "f20": "total_mv",
        "f21": "float_mv",
        "f22": "speed",
        "f23": "pb",
        "f24": "ret60_spot",
        "f25": "ytd_ret",
        "f62": "main_net_inflow",
        "f184": "main_net_ratio",
    }
    df = df.rename(columns=rename)
    df["code"] = df["code"].astype(str).str.zfill(6)
    for col in df.columns:
        if col not in {"code", "name"}:
            df[col] = pd.to_numeric(df[col].replace("-", np.nan), errors="coerce")
    return df


def latest_by_code(df: pd.DataFrame, code_col: str = "股票代码") -> pd.DataFrame:
    result = df.copy()
    result[code_col] = result[code_col].astype(str).str.zfill(6)
    date_cols = [c for c in result.columns if "公告日期" in c or "最新公告日期" in c]
    if date_cols:
        date_col = date_cols[0]
        result[date_col] = pd.to_datetime(result[date_col], errors="coerce")
        result = result.sort_values(date_col)
    return result.drop_duplicates(code_col, keep="last")


def get_financials() -> pd.DataFrame:
    import akshare as ak

    period = os.environ["FREETRADE_REPORT_PERIOD"]
    annual = os.environ["FREETRADE_ANNUAL_YEAR"]
    if len(period) != 8 or not period.isdigit() or len(annual) != 4 or not annual.isdigit():
        raise ValueError("invalid report period or annual year")
    datetime.strptime(period, "%Y%m%d")
    year = int(annual)
    q1 = latest_by_code(ak.stock_yjbb_em(date=period))
    q1 = q1.rename(
        columns={
            "股票代码": "code",
            "股票简称": "fin_name",
            "营业总收入-同比增长": "rev_yoy",
            "净利润-同比增长": "np_yoy",
            "净利润-净利润": "q1_net_profit",
            "净资产收益率": "roe",
            "销售毛利率": "gross_margin",
            "所处行业": "industry",
            "最新公告日期": "q1_report_date",
        }
    )
    keep = [
        "code",
        "fin_name",
        "rev_yoy",
        "np_yoy",
        "q1_net_profit",
        "roe",
        "gross_margin",
        "industry",
        "q1_report_date",
    ]
    q1 = q1[keep]

    xjll = latest_by_code(ak.stock_xjll_em(date=period))
    xjll = xjll.rename(
        columns={
            "股票代码": "code",
            "经营性现金流-现金流量净额": "q1_ocf",
        }
    )[["code", "q1_ocf"]]

    lrb_2025 = latest_by_code(ak.stock_lrb_em(date=f"{year}1231"))
    lrb_2025 = lrb_2025.rename(
        columns={
            "股票代码": "code",
            "营业总收入": "rev_2025",
            "净利润": "np_2025",
        }
    )[["code", "rev_2025", "np_2025"]]

    lrb_2022 = latest_by_code(ak.stock_lrb_em(date=f"{year - 3}1231"))
    lrb_2022 = lrb_2022.rename(
        columns={
            "股票代码": "code",
            "营业总收入": "rev_2022",
            "净利润": "np_2022",
        }
    )[["code", "rev_2022", "np_2022"]]

    fin = q1.merge(xjll, on="code", how="left").merge(lrb_2025, on="code", how="left").merge(
        lrb_2022, on="code", how="left"
    )
    fin["ocf_np"] = np.where(fin["q1_net_profit"] > 0, fin["q1_ocf"] / fin["q1_net_profit"], np.nan)
    fin["rev_cagr_3y"] = np.where(
        (fin["rev_2025"] > 0) & (fin["rev_2022"] > 0),
        (fin["rev_2025"] / fin["rev_2022"]) ** (1 / 3) - 1,
        np.nan,
    )
    fin["np_cagr_3y"] = np.where(
        (fin["np_2025"] > 0) & (fin["np_2022"] > 0),
        (fin["np_2025"] / fin["np_2022"]) ** (1 / 3) - 1,
        np.nan,
    )
    return fin


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    finite = s.replace([np.inf, -np.inf], np.nan)
    lo, hi = finite.quantile([0.01, 0.99])
    clipped = finite.clip(lower=lo, upper=hi)
    pct = clipped.rank(pct=True, method="average") * 100
    if not higher_is_better:
        pct = 100 - pct
    return pct


def kline_for(row: pd.Series) -> dict:
    code = row["code"]
    market = int(row["market"])
    secid = f"{market}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "klt": 101,
        "fqt": 1,
        "beg": os.environ.get("FREETRADE_HISTORY_START", "20251001"),
        "end": TODAY,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    try:
        data = em_json(url, params, retries=3)["data"]
        klines = data.get("klines") or []
        if not klines:
            return {"code": code, "history_ok": False}
        parts = [k.split(",") for k in klines]
        hist = pd.DataFrame(
            parts,
            columns=[
                "date",
                "open",
                "close",
                "high",
                "low",
                "volume",
                "amount",
                "amplitude",
                "pct_chg",
                "chg",
                "turnover",
            ],
        )
        for col in hist.columns:
            if col != "date":
                hist[col] = pd.to_numeric(hist[col], errors="coerce")
        hist = hist.dropna(subset=["close", "high", "low", "amount"])
        if len(hist) < 75:
            return {"code": code, "history_ok": False, "bars": len(hist)}

        close = hist["close"]
        high = hist["high"]
        low = hist["low"]
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr14_pct = (tr.rolling(14).mean().iloc[-1] / close.iloc[-1]) * 100
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        ma20_prev = close.rolling(20).mean().iloc[-6]
        trend_checks = [
            close.iloc[-1] > ma20,
            ma5 > ma10,
            ma10 > ma20,
            ma20 > ma60,
            ma20 > ma20_prev,
        ]
        win_streak = 0
        for idx in range(len(close) - 1, 0, -1):
            if close.iloc[idx] > close.iloc[idx - 1]:
                win_streak += 1
            else:
                break
        return {
            "code": code,
            "history_ok": True,
            "bars": len(hist),
            "last_k_date": hist["date"].iloc[-1],
            "ret20": (close.iloc[-1] / close.iloc[-21] - 1) * 100,
            "ret60": (close.iloc[-1] / close.iloc[-61] - 1) * 100,
            "avg20_amount": hist["amount"].tail(20).mean(),
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "ma_trend_score": sum(trend_checks) / len(trend_checks) * 100,
            "atr14_pct": atr14_pct,
            "win_streak": win_streak,
            "hist_close": close.iloc[-1],
        }
    except Exception as exc:
        return {"code": code, "history_ok": False, "history_error": str(exc)[:120]}


def add_history(candidates: pd.DataFrame, limit: int = 1000) -> pd.DataFrame:
    rows = candidates.head(limit).to_dict("records")
    history_rows = []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("FREETRADE_WORKERS", "8"))) as pool:
        futures = [pool.submit(kline_for, pd.Series(row)) for row in rows]
        for fut in as_completed(futures):
            history_rows.append(fut.result())
    hist = pd.DataFrame(history_rows)
    return candidates.merge(hist, on="code", how="left")


def load_market_boards() -> tuple[pd.DataFrame, pd.DataFrame]:
    import akshare as ak

    concept = ak.stock_board_concept_name_em()
    fund = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    return concept, fund


def build() -> tuple[pd.DataFrame, dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spot = get_spot()
    fin = get_financials()
    concept, sector_fund = load_market_boards()

    df = spot.merge(fin, on="code", how="left")
    df["name"] = df["name"].fillna(df["fin_name"])
    df["amount_ratio_float_mv"] = df["main_net_inflow"] / df["float_mv"] * 100
    df["peg_q1_np_yoy"] = np.where(
        (df["pe_dynamic"] > 0) & (df["np_yoy"] > 0),
        df["pe_dynamic"] / df["np_yoy"],
        np.nan,
    )

    name = df["name"].astype(str)
    base = df[
        (df["price"] > 0)
        & (df["amount"] >= 100_000_000)
        & (~name.str.contains("ST|退", case=False, regex=True, na=False))
        & (~name.str.match(r"^[NC]", na=False))
        & (df["pe_dynamic"] > 0)
        & (df["pb"] > 0)
        & (df["q1_net_profit"] > 0)
        & (df["rev_yoy"].notna())
        & (df["np_yoy"].notna())
        & (df["roe"].notna())
        & (df["gross_margin"].notna())
        & (df["rev_cagr_3y"].notna())
    ].copy()

    base["pe_score"] = percentile_score(base["pe_dynamic"], higher_is_better=False)
    base["pb_score"] = percentile_score(base["pb"], higher_is_better=False)
    base["peg_score"] = percentile_score(base["peg_q1_np_yoy"], higher_is_better=False)
    base["value_score"] = base[["pe_score", "pb_score", "peg_score"]].mean(axis=1, skipna=True)

    base["rev_yoy_score"] = percentile_score(base["rev_yoy"], higher_is_better=True)
    base["np_yoy_score"] = percentile_score(base["np_yoy"], higher_is_better=True)
    base["rev_cagr_score"] = percentile_score(base["rev_cagr_3y"], higher_is_better=True)
    base["growth_score"] = base[["rev_yoy_score", "np_yoy_score", "rev_cagr_score"]].mean(axis=1)

    base["roe_score"] = percentile_score(base["roe"], higher_is_better=True)
    base["gm_score"] = percentile_score(base["gross_margin"], higher_is_better=True)
    base["ocf_np_score"] = percentile_score(base["ocf_np"], higher_is_better=True)
    base["quality_score"] = base[["roe_score", "gm_score", "ocf_np_score"]].mean(axis=1, skipna=True)

    base["ret60_spot_score"] = percentile_score(base["ret60_spot"], higher_is_better=True)
    base["turnover_score"] = percentile_score(base["turnover"], higher_is_better=True)
    base["momentum_pre_score"] = base[["ret60_spot_score", "turnover_score"]].mean(axis=1)

    base["main_net_ratio_score"] = percentile_score(base["main_net_ratio"], higher_is_better=True)
    base["main_float_score"] = percentile_score(base["amount_ratio_float_mv"], higher_is_better=True)
    base["fund_score"] = base[["main_net_ratio_score", "main_float_score"]].mean(axis=1, skipna=True)

    base["pre_score"] = (
        0.16 * base["value_score"]
        + 0.22 * base["growth_score"]
        + 0.17 * base["quality_score"]
        + 0.25 * base["momentum_pre_score"]
        + 0.20 * base["fund_score"]
    )
    base = base.sort_values("pre_score", ascending=False)

    enriched = add_history(base, limit=1200)
    final = enriched[(enriched["history_ok"] == True) & (enriched["avg20_amount"] >= 100_000_000)].copy()
    final["ret20_score"] = percentile_score(final["ret20"], higher_is_better=True)
    final["ret60_score"] = percentile_score(final["ret60"], higher_is_better=True)
    final["ma_score"] = final["ma_trend_score"]
    final["momentum_score"] = final[["ret20_score", "ret60_score", "ma_score"]].mean(axis=1)

    final["score_raw"] = (
        0.16 * final["value_score"]
        + 0.22 * final["growth_score"]
        + 0.17 * final["quality_score"]
        + 0.25 * final["momentum_score"]
        + 0.20 * final["fund_score"]
    )
    final["risk_multiplier"] = 1.0
    final.loc[final["atr14_pct"] > 8, "risk_multiplier"] *= 0.92
    final.loc[final["atr14_pct"] > 10, "risk_multiplier"] *= 0.90
    final.loc[final["win_streak"] > 5, "risk_multiplier"] *= 0.90
    final.loc[final["ret20"] > 50, "risk_multiplier"] *= 0.94
    final["score"] = final["score_raw"] * final["risk_multiplier"]

    final = final.sort_values("score", ascending=False)
    selected_rows = []
    industry_counts: dict[str, int] = {}
    for _, row in final.iterrows():
        industry = row["industry"] if isinstance(row["industry"], str) and row["industry"] else "未知"
        if industry_counts.get(industry, 0) >= 3:
            continue
        selected_rows.append(row)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        if len(selected_rows) == 20:
            break
    selected = pd.DataFrame(selected_rows)

    final_cols = [
        "code",
        "name",
        "industry",
        "score",
        "score_raw",
        "risk_multiplier",
        "value_score",
        "growth_score",
        "quality_score",
        "momentum_score",
        "fund_score",
        "price",
        "pct_chg",
        "amount",
        "avg20_amount",
        "pe_dynamic",
        "pb",
        "peg_q1_np_yoy",
        "rev_yoy",
        "np_yoy",
        "rev_cagr_3y",
        "roe",
        "gross_margin",
        "ocf_np",
        "ret20",
        "ret60",
        "ma_trend_score",
        "atr14_pct",
        "win_streak",
        "main_net_inflow",
        "main_net_ratio",
        "amount_ratio_float_mv",
        "q1_report_date",
        "last_k_date",
    ]
    selected[final_cols].to_csv(OUT_DIR / f"a_share_top20_{RUN_DATE}.csv", index=False)
    final[final_cols].head(200).to_csv(OUT_DIR / f"a_share_scored_candidates_{RUN_DATE}.csv", index=False)
    concept.head(30).to_csv(OUT_DIR / f"a_share_concept_boards_{RUN_DATE}.csv", index=False)
    sector_fund.head(30).to_csv(OUT_DIR / f"a_share_sector_fund_flow_{RUN_DATE}.csv", index=False)
    selected[final_cols].to_csv(OUT_DIR / "a_share_top20_latest.csv", index=False)
    final[final_cols].head(200).to_csv(OUT_DIR / "a_share_scored_candidates_latest.csv", index=False)
    concept.head(30).to_csv(OUT_DIR / "a_share_concept_boards_latest.csv", index=False)
    sector_fund.head(30).to_csv(OUT_DIR / "a_share_sector_fund_flow_latest.csv", index=False)

    valid_spot = spot[(spot["price"].notna()) & (spot["price"] > 0)]
    metadata = {
        "run_date": RUN_DATE,
        "spot_rows": len(spot),
        "valid_spot_rows": len(valid_spot),
        "up_count": int((valid_spot["pct_chg"] > 0).sum()),
        "flat_count": int((valid_spot["pct_chg"] == 0).sum()),
        "down_count": int((valid_spot["pct_chg"] < 0).sum()),
        "limit_upish_count": int((valid_spot["pct_chg"] >= 9.8).sum()),
        "limit_downish_count": int((valid_spot["pct_chg"] <= -9.8).sum()),
        "market_amount": float(valid_spot["amount"].sum()),
        "median_pct_chg": float(valid_spot["pct_chg"].median()),
        "mean_pct_chg": float(valid_spot["pct_chg"].mean()),
        "base_rows": len(base),
        "history_enriched_rows": int(enriched["history_ok"].fillna(False).sum()),
        "final_rows": len(final),
        "selected_rows": len(selected),
        "top_concepts": concept.head(10).to_dict("records"),
        "top_sector_fund": sector_fund.head(10).to_dict("records"),
    }
    return selected, metadata


if __name__ == "__main__":
    selected_df, meta = build()
    print("META", meta)
    pd.set_option("display.max_columns", 80)
    print(selected_df.head(20).to_string(index=False))
