"""
Reclassification OOS — Re-backtest les 13 strategies validees avec extraction PF.
Applique les nouveaux criteres Tier 1/2/3.
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = str(PROJECT_ROOT / "freqtrade" / "config_backtest_kraken.json")
STRATEGY_PATH = str(PROJECT_ROOT / "freqtrade" / "strategies")
OOS_TIMERANGE = "20251201-20260319"

VALIDATED_STRATEGIES = [
    "RSIDivergence",
    "MACDDivergence",
    "SmartMoneyConcepts",
    "ADXRegimeFilter",
    "OBVDivergence",
    "ZScoreMeanReversion",
    "RangeBreakoutVolume",
    "EMATripleCross",
    "MARibbonStack",
    "TripleScreenElder",
    "MoneyFlowIndex",
    "WyckoffAccumulation",
    "VolatilityBreakout",
]

ALL_WEATHER = {
    "RSIDivergence", "MACDDivergence", "SmartMoneyConcepts",
    "OBVDivergence", "EMATripleCross", "MARibbonStack",
}


def run_backtest(strategy: str) -> str:
    cmd = [
        "rtk", "freqtrade", "backtesting",
        "--strategy", strategy,
        "-c", CONFIG,
        "--strategy-path", STRATEGY_PATH,
        "--timerange", OOS_TIMERANGE,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return result.stdout + result.stderr


def parse_result(output: str) -> dict:
    r = {
        "trades": 0, "profit_pct": 0.0, "win_rate": 0.0,
        "drawdown_pct": 0.0, "profit_factor": 0.0,
        "sharpe": 0.0, "sortino": 0.0, "wins": 0, "losses": 0,
    }

    # STRATEGY SUMMARY line
    m = re.search(
        r"│\s+\w+\s+│\s+(\d+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│"
        r"\s+([\d:, a-z]+)\s+│\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+│\s+([-\d.]+)\s+USDT\s+([-\d.]+)%",
        output,
    )
    if m:
        r["trades"] = int(m.group(1))
        r["profit_pct"] = float(m.group(4))
        r["wins"] = int(m.group(6))
        r["losses"] = int(m.group(8))
        r["win_rate"] = float(m.group(9))
        r["drawdown_pct"] = float(m.group(11))

    # Profit factor
    pf = re.search(r"Profit factor\s+│\s+([-\d.]+|inf)", output)
    if pf:
        r["profit_factor"] = 999.0 if pf.group(1) == "inf" else float(pf.group(1))

    # Fix: freqtrade reports PF=0.00 when no losses (should be inf)
    if r["profit_factor"] == 0.0 and r["losses"] == 0 and r["profit_pct"] > 0:
        r["profit_factor"] = 999.0

    # Sharpe
    sh = re.search(r"Sharpe\s+│\s+([-\d.]+)", output)
    if sh:
        r["sharpe"] = float(sh.group(1))

    # Sortino
    so = re.search(r"Sortino\s+│\s+([-\d.]+)", output)
    if so:
        r["sortino"] = float(so.group(1))

    return r


def classify(r: dict) -> str:
    if r["trades"] == 0 or r["profit_pct"] <= 0 or r["drawdown_pct"] > 25 or r["profit_factor"] < 1.0:
        return "ECHEC"

    wr = r["win_rate"]

    # Tier 1
    min_trades_t1 = 5 if wr >= 80 else 10
    if (r["profit_pct"] >= 17.5 and r["drawdown_pct"] < 15
            and r["profit_factor"] >= 2.0 and r["trades"] >= min_trades_t1):
        return "TIER 1"

    # Tier 2
    min_trades_t2 = 3 if wr >= 80 else 8
    if (r["profit_pct"] >= 10.5 and r["drawdown_pct"] < 20
            and r["profit_factor"] >= 1.5 and r["trades"] >= min_trades_t2):
        return "TIER 2"

    # Tier 3
    if r["profit_pct"] > 0 and r["drawdown_pct"] < 25 and r["profit_factor"] > 1.0:
        return "TIER 3"

    return "ECHEC"


def main():
    results = []

    for strat in VALIDATED_STRATEGIES:
        print(f"[OOS] {strat}...", end=" ", flush=True)
        output = run_backtest(strat)
        r = parse_result(output)
        tier = classify(r)
        aw = "OUI" if strat in ALL_WEATHER else "NON"
        results.append((strat, r, tier, aw))
        print(f"Profit={r['profit_pct']:.2f}% PF={r['profit_factor']:.2f} "
              f"WR={r['win_rate']:.1f}% DD={r['drawdown_pct']:.2f}% → {tier}")

    # Summary table
    print("\n" + "=" * 100)
    print("RECLASSIFICATION OOS — Criteres 3-5%/mois")
    print("=" * 100)
    print(f"{'#':<3} {'Strategie':<25} {'OOS%':>8} {'PF':>6} {'WR%':>6} {'DD%':>6} "
          f"{'Trades':>7} {'Sharpe':>7} {'AW':>4} {'Tier':<8}")
    print("-" * 100)

    for i, (strat, r, tier, aw) in enumerate(results, 1):
        pf_str = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 999 else "inf"
        print(f"{i:<3} {strat:<25} {r['profit_pct']:>7.2f}% {pf_str:>6} {r['win_rate']:>5.1f}% "
              f"{r['drawdown_pct']:>5.2f}% {r['trades']:>7} {r['sharpe']:>7.2f} {aw:>4} {tier:<8}")

    # Count tiers
    tiers = {"TIER 1": 0, "TIER 2": 0, "TIER 3": 0, "ECHEC": 0}
    for _, _, tier, _ in results:
        tiers[tier] += 1

    print("-" * 100)
    print(f"Tier 1 (dry-run): {tiers['TIER 1']} | Tier 2 (portfolio): {tiers['TIER 2']} "
          f"| Tier 3 (surveiller): {tiers['TIER 3']} | Echec: {tiers['ECHEC']}")


if __name__ == "__main__":
    main()
