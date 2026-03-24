"""
Regime Tournament — Teste toutes les strategies Lite par regime de marche.

Pour chaque strategie x regime → backtest → score composite.
Selectionne le top 1 par regime (haussier, baissier, stable).

Usage:
    python scripts/regime_tournament.py [--strategies-only] [--report-only]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = str(PROJECT_ROOT / "freqtrade" / "config_backtest_kraken.json")
STRATEGY_PATH = str(PROJECT_ROOT / "freqtrade" / "strategies")
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DETECTED_REGIMES_FILE = REPORTS_DIR / "detected_regimes.json"
RESULTS_FILE = REPORTS_DIR / "regime_tournament_results.json"

# Toutes les strategies Lite a tester
ALL_LITE = [
    "RSIDivergenceLite",
    "MACDDivergenceLite",
    "OBVDivergenceLite",
    "EMATripleCrossLite",
    "IchimokuBreakoutLite",
    "MARibbonStackLite",
    "DCASimple",
    "ZScoreMeanReversionLite",
    "BollingerMACDReversalLite",
    "StochasticMomentumIndexLite",
    "ChoppinessBreakoutLite",
    "KeltnerChannelMomentumLite",
    "DMICrossoverLite",
    "ChandelierExitLite",
    "SuperTrendADXLite",
    "MoneyFlowIndexLite",
    "AwesomeOscillatorLite",
    "TripleScreenElderLite",
    "CCIMomentumTrendLite",
]

BACKTEST_TIMEOUT = 600


def load_regimes() -> dict[str, str]:
    """Charge les periodes de regime depuis detected_regimes.json."""
    with open(DETECTED_REGIMES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    selected = data["selected_timeranges"]
    return {k: v for k, v in selected.items() if k != "transition"}


def run_backtest(strategy: str, timerange: str) -> dict:
    """Lance un backtest et parse les resultats."""
    cmd = [
        "rtk", "freqtrade", "backtesting",
        "--config", CONFIG,
        "--strategy", strategy,
        "--strategy-path", STRATEGY_PATH,
        "--timerange", timerange,
        "--timeframe", "4h",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=BACKTEST_TIMEOUT, cwd=str(PROJECT_ROOT),
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return {"error": "TIMEOUT", "trades": 0, "profit_pct": 0.0, "profit_factor": 0.0, "drawdown_pct": 0.0, "win_rate": 0.0, "sharpe": 0.0}
    except Exception as e:
        return {"error": str(e), "trades": 0, "profit_pct": 0.0, "profit_factor": 0.0, "drawdown_pct": 0.0, "win_rate": 0.0, "sharpe": 0.0}

    return parse_result(output)


def parse_result(output: str) -> dict:
    """Parse la sortie freqtrade backtest."""
    result = {
        "trades": 0, "profit_pct": 0.0, "profit_factor": 0.0,
        "drawdown_pct": 0.0, "win_rate": 0.0, "sharpe": 0.0,
    }

    strategy_line = re.search(
        r"│\s+\w+\s+│\s+(\d+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│\s+([\w\s,:]+?)\s+│\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+│",
        output,
    )
    if strategy_line:
        result["trades"] = int(strategy_line.group(1))
        result["profit_pct"] = float(strategy_line.group(4))
        wins = int(strategy_line.group(6))
        losses = int(strategy_line.group(8))
        total = wins + losses
        result["win_rate"] = (wins / total * 100) if total > 0 else 0.0

    pf_match = re.search(r"Profit factor\s+│\s+([-\d.]+)", output)
    if pf_match:
        result["profit_factor"] = float(pf_match.group(1))

    dd_match = re.search(r"Max.*Drawdown.*│\s+([-\d.]+)%", output)
    if dd_match:
        result["drawdown_pct"] = abs(float(dd_match.group(1)))

    sharpe_match = re.search(r"Sharpe\s+│\s+([-\d.]+)", output)
    if sharpe_match:
        result["sharpe"] = float(sharpe_match.group(1))

    return result


def compute_score(r: dict) -> float:
    """Score composite : PF * (1 - DD/100) * min(trades, 20)/20."""
    if r["trades"] == 0 or r["profit_factor"] <= 0:
        return 0.0
    dd_factor = max(0, 1 - r["drawdown_pct"] / 100)
    trade_factor = min(r["trades"], 20) / 20
    return r["profit_factor"] * dd_factor * trade_factor


def run_tournament() -> dict:
    """Execute le tournament complet."""
    regimes = load_regimes()
    print(f"Regimes charges: {list(regimes.keys())}")
    for regime, tr in regimes.items():
        print(f"  {regime}: {tr}")

    all_results = {}

    for regime, timerange in regimes.items():
        print(f"\n{'='*60}")
        print(f"REGIME: {regime.upper()} ({timerange})")
        print(f"{'='*60}")

        regime_results = []
        for strat in ALL_LITE:
            print(f"  {strat}...", end=" ", flush=True)
            r = run_backtest(strat, timerange)
            r["score"] = compute_score(r)
            r["strategy"] = strat
            regime_results.append(r)
            print(f"trades={r['trades']}, profit={r['profit_pct']:.2f}%, PF={r['profit_factor']:.2f}, score={r['score']:.3f}")

        regime_results.sort(key=lambda x: x["score"], reverse=True)
        all_results[regime] = regime_results

    return all_results


def generate_report(all_results: dict) -> str:
    """Genere le rapport markdown du tournament."""
    lines = [
        f"# Regime Tournament — {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    winners = {}

    for regime, results in all_results.items():
        lines.append(f"## Regime: {regime.upper()}")
        lines.append("")
        lines.append("| # | Strategie | Trades | Profit% | PF | DD% | WR% | Sharpe | Score |")
        lines.append("|---|-----------|--------|---------|-----|-----|-----|--------|-------|")

        for i, r in enumerate(results):
            prefix = "**" if i == 0 else ""
            suffix = "**" if i == 0 else ""
            lines.append(
                f"| {i+1} | {prefix}{r['strategy']}{suffix} | {r['trades']} | "
                f"{r['profit_pct']:+.2f} | {r['profit_factor']:.2f} | "
                f"{r['drawdown_pct']:.2f} | {r['win_rate']:.1f} | "
                f"{r['sharpe']:.2f} | {r['score']:.3f} |"
            )

        if results and results[0]["score"] > 0:
            winners[regime] = results[0]["strategy"]
        lines.append("")

    lines.append("## Selection finale")
    lines.append("")
    lines.append("| Regime | Meilleure strategie | Score |")
    lines.append("|--------|-------------------|-------|")
    for regime, results in all_results.items():
        best = results[0] if results else {"strategy": "AUCUN", "score": 0}
        lines.append(f"| {regime} | **{best['strategy']}** | {best['score']:.3f} |")

    return "\n".join(lines)


def main():
    report_only = "--report-only" in sys.argv

    if report_only and RESULTS_FILE.exists():
        with open(RESULTS_FILE, encoding="utf-8") as f:
            all_results = json.load(f)
    else:
        all_results = run_tournament()
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\nResultats sauvegardes: {RESULTS_FILE}")

    report = generate_report(all_results)
    report_file = REPORTS_DIR / "regime_tournament_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Rapport: {report_file}")
    print(report)


if __name__ == "__main__":
    main()
