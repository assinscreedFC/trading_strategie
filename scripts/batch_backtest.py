"""
Batch Backtest Runner — Teste toutes les strategies sur differentes conditions de marche.

Usage:
    python scripts/batch_backtest.py [--phase initial|hyperopt|oos|regime|all] [--batch 1|2|3]

Phases:
    initial  — Backtest 12 mois pour toutes les strategies
    hyperopt — Hyperopt 1000 epochs (Batch 1: rentables seulement, Batch 2: TOUTES)
    oos      — Walk-forward OOS pour les strategies optimisees
    regime   — Test par regime de marche (auto-detecte si disponible)
    all      — Toutes les phases sequentiellement
"""

import csv
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Configuration ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = str(PROJECT_ROOT / "freqtrade" / "config_backtest_kraken.json")
STRATEGY_PATH = str(PROJECT_ROOT / "freqtrade" / "strategies")
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

BATCH_1_STRATEGIES = [
    "RSI2Connors",
    "CumulativeRSI",
    "ConnorsRSI",
    "ADOSCTrailing",
    "TwiggsMoneyFlow",
    "CombinedBinHAndClucV8",
    "ADXRegimeFilter",
    "VWMASMACross",
    "ElderImpulse",
    "AwesomeOscillator",
]

BATCH_2_STRATEGIES = [
    "KeltnerChannelMomentum",
    "StochasticMomentumIndex",
    "PivotPointReversal",
    "DMICrossover",
    "ChoppinessBreakout",
    "RSIDivergence",
    "ZScoreMeanReversion",
    "TripleScreenElder",
    "ChandelierExit",
    "MoneyFlowIndex",
]

BATCH_3_STRATEGIES = [
    "IchimokuBreakout",
    "SuperTrendADX",
    "FibonacciPullback",
    "HeikinAshiTrend",
    "KAMAAdaptiveTrend",
    "CCIMomentumTrend",
    "BollingerMACDReversal",
    "OBVTrendConfirm",
    "RSIRangeMeanRevert",
    "VolumeProfileAccumulation",
]

VALIDATED_STRATEGIES = [
    "MACDDivergence",
    "SmartMoneyConcepts",
    "OBVDivergence",
    "RangeBreakoutVolume",
    "EMATripleCross",
    "MARibbonStack",
    "WyckoffAccumulation",
    "VolatilityBreakout",
    "ADXRegimeFilter",
    "RSIDivergence",
    "ZScoreMeanReversion",
    "TripleScreenElder",
    "MoneyFlowIndex",
]

FULL_TIMERANGE = "20250301-20260301"
OOS_TIMERANGE = "20251201-20260319"

# Regimes de marche hardcodes (fallback si auto-detection non disponible)
MARKET_REGIMES_HARDCODED = {
    "haussier": "20250301-20250601",
    "baissier": "20250601-20250901",
    "stable": "20250901-20251201",
    "full_12m": FULL_TIMERANGE,
}

DETECTED_REGIMES_FILE = REPORTS_DIR / "detected_regimes.json"


def load_market_regimes() -> dict:
    """Charge les regimes auto-detectes, fallback sur hardcodes."""
    if DETECTED_REGIMES_FILE.exists():
        try:
            with open(DETECTED_REGIMES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            selected = data.get("selected_timeranges", {})
            if selected:
                regimes = {k: v for k, v in selected.items() if k != "transition"}
                regimes["full_12m"] = FULL_TIMERANGE
                print(f"  Regimes auto-detectes charges depuis {DETECTED_REGIMES_FILE.name}")
                for regime, tr in regimes.items():
                    if regime != "full_12m":
                        print(f"    {regime}: {tr}")
                return regimes
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Erreur lecture regimes: {e}")

    print("  Utilisation des regimes hardcodes (fallback)")
    return MARKET_REGIMES_HARDCODED.copy()


MARKET_REGIMES = load_market_regimes()

BACKTEST_TIMEOUT = 600  # 10 min max par backtest
HYPEROPT_TIMEOUT = 3600  # 60 min max par hyperopt


def run_command(cmd: list[str], timeout: int = BACKTEST_TIMEOUT) -> tuple[str, int]:
    """Execute une commande avec timeout et cleanup propre."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired as e:
        print(f"  TIMEOUT apres {timeout}s")
        return f"TIMEOUT after {timeout}s", 1
    except Exception as e:
        return f"ERROR: {e}", 1


def parse_backtest_result(output: str) -> dict:
    """Parse la sortie freqtrade backtest pour extraire les metriques."""
    result = {
        "trades": 0,
        "avg_profit_pct": 0.0,
        "tot_profit_usdt": 0.0,
        "tot_profit_pct": 0.0,
        "avg_duration": "",
        "win_rate": 0.0,
        "wins": 0,
        "losses": 0,
        "drawdown_pct": 0.0,
        "drawdown_usdt": 0.0,
        "profit_factor": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "max_dd_duration": "",
        "expectancy": 0.0,
        "max_consecutive_losses": 0,
    }

    # Parse STRATEGY SUMMARY line
    # Duration format varies: "0:00:00", "1 day, 7:36:00", "2 days, 3:12:00"
    strategy_line = re.search(
        r"│\s+\w+\s+│\s+(\d+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│\s+([-\d.]+)\s+│\s+([\w\s,:]+?)\s+│\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+│\s+([-\d.]+)\s+USDT\s+([-\d.]+)%",
        output,
    )
    if strategy_line:
        result["trades"] = int(strategy_line.group(1))
        result["avg_profit_pct"] = float(strategy_line.group(2))
        result["tot_profit_usdt"] = float(strategy_line.group(3))
        result["tot_profit_pct"] = float(strategy_line.group(4))
        result["avg_duration"] = strategy_line.group(5)
        result["wins"] = int(strategy_line.group(6))
        result["losses"] = int(strategy_line.group(8))
        result["win_rate"] = float(strategy_line.group(9))
        result["drawdown_usdt"] = float(strategy_line.group(10))
        result["drawdown_pct"] = float(strategy_line.group(11))

    # Profit factor
    pf_match = re.search(r"Profit factor\s+│\s+([-\d.]+|inf)", output)
    if pf_match and pf_match.group(1) != "inf":
        result["profit_factor"] = float(pf_match.group(1))

    # Sharpe
    sharpe_match = re.search(r"Sharpe\s+│\s+([-\d.]+)", output)
    if sharpe_match:
        result["sharpe"] = float(sharpe_match.group(1))

    # Sortino
    sortino_match = re.search(r"Sortino\s+│\s+([-\d.]+)", output)
    if sortino_match:
        result["sortino"] = float(sortino_match.group(1))

    # Max consecutive losses
    consec_match = re.search(r"Max Consecutive Wins / Loss\s+│\s+\d+\s*/\s*(\d+)", output)
    if consec_match:
        result["max_consecutive_losses"] = int(consec_match.group(1))

    # DD duration
    dd_dur_match = re.search(r"Drawdown duration\s+│\s+(.+?)│", output)
    if dd_dur_match:
        result["max_dd_duration"] = dd_dur_match.group(1).strip()

    # Expectancy
    if result["trades"] > 0:
        result["expectancy"] = result["tot_profit_pct"] / result["trades"]

    return result


def run_backtest(strategy: str, timerange: str) -> dict:
    """Lance un backtest et retourne les resultats parses."""
    cmd = [
        "rtk", "freqtrade", "backtesting",
        "--strategy", strategy,
        "-c", CONFIG,
        "--strategy-path", STRATEGY_PATH,
        "--timerange", timerange,
    ]
    print(f"  Backtest {strategy} [{timerange}]...", end=" ", flush=True)
    output, rc = run_command(cmd)

    if rc != 0 and "No data left" in output:
        print("SKIP (pas assez de donnees)")
        return {"error": "no_data"}

    if rc != 0:
        print(f"ERREUR (rc={rc})")
        return {"error": output[:200]}

    result = parse_backtest_result(output)
    print(f"OK — {result['trades']} trades, {result['tot_profit_pct']:.2f}%, DD {result['drawdown_pct']:.2f}%")
    return result


def run_hyperopt(strategy: str, epochs: int = 1000) -> dict:
    """Lance un hyperopt et retourne les meilleurs params."""
    cmd = [
        "rtk", "freqtrade", "hyperopt",
        "--strategy", strategy,
        "-c", CONFIG,
        "--strategy-path", STRATEGY_PATH,
        "--timerange", FULL_TIMERANGE,
        "--hyperopt-loss", "SharpeHyperOptLossDaily",
        "--epochs", str(epochs),
        "-j", "2",
    ]
    print(f"  Hyperopt {strategy} ({epochs} epochs)...", end=" ", flush=True)
    output, rc = run_command(cmd, timeout=HYPEROPT_TIMEOUT)

    if rc != 0:
        print(f"ERREUR (rc={rc})")
        return {"error": output[:200]}

    # Parse best result
    best_match = re.search(r"Best result:\s+.*?Profit:\s+([-\d.]+)%", output)
    if best_match:
        profit = float(best_match.group(1))
        print(f"OK — meilleur: {profit:.2f}%")
        return {"best_profit": profit, "output": output[-2000:]}

    print("OK (resultat non parse)")
    return {"output": output[-2000:]}


def generate_report(all_results: dict, filename: str = "batch1_report.md") -> None:
    """Genere un rapport markdown avec tous les resultats."""
    report_path = REPORTS_DIR / filename
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Rapport Batch 1 — {timestamp}",
        "",
        "## Resultats par strategie et regime de marche",
        "",
    ]

    # Header tableau
    lines.append("| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |")
    lines.append("|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|")

    for strategy, regimes in sorted(all_results.items()):
        for regime, result in sorted(regimes.items()):
            # Skip non-backtest entries (hyperopt metadata, etc.)
            if not isinstance(result, dict) or "trades" not in result:
                if isinstance(result, dict) and "error" in result:
                    lines.append(f"| {strategy} | {regime} | — | — | — | — | — | — | — | — |")
                continue
            lines.append(
                f"| {strategy} | {regime} | {result['trades']} | "
                f"{result['tot_profit_pct']:.2f} | {result['drawdown_pct']:.2f} | "
                f"{result['win_rate']:.1f} | {result['profit_factor']:.2f} | "
                f"{result['sharpe']:.2f} | {result['expectancy']:.2f} | "
                f"{result['max_consecutive_losses']} |"
            )

    # Classement
    lines.extend(["", "## Classement (12 mois, trie par profit)", ""])
    full_results = []
    for strategy, regimes in all_results.items():
        if "full_12m" in regimes and "error" not in regimes["full_12m"]:
            full_results.append((strategy, regimes["full_12m"]))

    full_results.sort(key=lambda x: x[1]["tot_profit_pct"], reverse=True)
    lines.append("| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |")
    lines.append("|---|-----------|---------|-----|-----|-----|--------|--------|")
    for i, (strat, r) in enumerate(full_results, 1):
        lines.append(
            f"| {i} | {strat} | {r['tot_profit_pct']:.2f} | "
            f"{r['drawdown_pct']:.2f} | {r['win_rate']:.1f} | "
            f"{r['profit_factor']:.2f} | {r['sharpe']:.2f} | {r['trades']} |"
        )

    # Strategies validees OOS
    lines.extend(["", "## Validation OOS", ""])
    lines.append("| Strategie | Profit OOS% | DD OOS% | WR% | Trades | Status |")
    lines.append("|-----------|-------------|---------|-----|--------|--------|")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRapport sauvegarde: {report_path}")

    # CSV aussi
    csv_path = REPORTS_DIR / filename.replace(".md", ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["strategy", "regime", "trades", "profit_pct", "drawdown_pct",
                         "win_rate", "profit_factor", "sharpe", "sortino", "expectancy",
                         "max_consecutive_losses", "avg_duration"])
        for strategy, regimes in sorted(all_results.items()):
            for regime, result in sorted(regimes.items()):
                if not isinstance(result, dict) or "trades" not in result:
                    continue
                writer.writerow([
                    strategy, regime, result["trades"], result["tot_profit_pct"],
                    result["drawdown_pct"], result["win_rate"], result["profit_factor"],
                    result["sharpe"], result["sortino"], result["expectancy"],
                    result["max_consecutive_losses"], result["avg_duration"],
                ])
    print(f"CSV sauvegarde: {csv_path}")


def phase_initial(strategies: list[str]) -> dict:
    """Phase 1: Backtest 12 mois pour toutes les strategies."""
    print("\n" + "=" * 60)
    print("PHASE 1 — BACKTESTS INITIAUX (12 mois)")
    print("=" * 60)

    results = {}
    for strat in strategies:
        results[strat] = {"full_12m": run_backtest(strat, FULL_TIMERANGE)}
    return results


def phase_hyperopt(results: dict, hyperopt_all: bool = False) -> dict:
    """Phase 2: Hyperopt pour les strategies.

    Args:
        hyperopt_all: Si True, hyperopt TOUTES les strategies (Batch 2 mode).
                      Si False, seulement les rentables (Batch 1 mode).
    """
    print("\n" + "=" * 60)
    print("PHASE 2 — HYPEROPT (1000 epochs)")
    print("=" * 60)

    if hyperopt_all:
        to_hyperopt = list(results.keys())
        print(f"  Mode TOUTES : {len(to_hyperopt)} strategies")
    else:
        to_hyperopt = [
            s for s, r in results.items()
            if "full_12m" in r
            and "error" not in r["full_12m"]
            and r["full_12m"]["tot_profit_pct"] > 0
        ]
        if not to_hyperopt:
            print("  Aucune strategie rentable, skip hyperopt.")
            return results
        print(f"  Strategies rentables: {', '.join(to_hyperopt)}")

    for strat in to_hyperopt:
        hyperopt_result = run_hyperopt(strat, epochs=1000)
        results[strat]["hyperopt"] = hyperopt_result

        # Re-backtest apres hyperopt
        if "error" not in hyperopt_result:
            results[strat]["full_12m_post_hyperopt"] = run_backtest(strat, FULL_TIMERANGE)

    return results


def phase_oos(results: dict) -> dict:
    """Phase 3: Walk-forward OOS."""
    print("\n" + "=" * 60)
    print("PHASE 3 — WALK-FORWARD OOS")
    print("=" * 60)

    # Tester toutes les strategies qui ont ete hyperopt
    for strat in list(results.keys()):
        if "hyperopt" in results[strat] and "error" not in results[strat].get("hyperopt", {"error": True}):
            results[strat]["oos"] = run_backtest(strat, OOS_TIMERANGE)

    return results


def phase_regime(results: dict, strategies: list[str]) -> dict:
    """Phase 4: Test par regime de marche."""
    print("\n" + "=" * 60)
    print("PHASE 4 — TESTS PAR REGIME DE MARCHE")
    print("=" * 60)

    for strat in strategies:
        if strat not in results:
            results[strat] = {}
        for regime_name, timerange in MARKET_REGIMES.items():
            if regime_name == "full_12m" and "full_12m" in results.get(strat, {}):
                continue  # Deja fait
            results[strat][regime_name] = run_backtest(strat, timerange)

    return results


def parse_args() -> tuple:
    """Parse les arguments CLI."""
    phase = "all"
    batch = 1

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--phase" and i + 1 < len(args):
            phase = args[i + 1]
            i += 2
        elif args[i].startswith("--phase="):
            phase = args[i].split("=")[1]
            i += 1
        elif args[i] == "--batch" and i + 1 < len(args):
            batch = int(args[i + 1])
            i += 2
        elif args[i].startswith("--batch="):
            batch = int(args[i].split("=")[1])
            i += 1
        else:
            # Legacy: premier arg sans flag = phase
            phase = args[i]
            i += 1

    return phase, batch


def main():
    phase, batch = parse_args()

    print(f"\n{'=' * 60}")
    print(f"BATCH {batch} — Phase: {phase}")
    print(f"{'=' * 60}")

    if batch == 3:
        strategies = BATCH_3_STRATEGIES
        hyperopt_all = True  # Batch 3: hyperopt TOUTES les strategies
        prefix = "batch3"
    elif batch == 2:
        strategies = BATCH_2_STRATEGIES
        hyperopt_all = True  # Batch 2: hyperopt TOUTES les strategies
        prefix = "batch2"
    else:
        strategies = BATCH_1_STRATEGIES
        hyperopt_all = False
        prefix = "batch1"

    all_results = {}

    if phase in ("initial", "all"):
        all_results = phase_initial(strategies)
        generate_report(all_results, f"{prefix}_initial.md")

    if phase in ("hyperopt", "all"):
        if not all_results:
            all_results = phase_initial(strategies)
        all_results = phase_hyperopt(all_results, hyperopt_all=hyperopt_all)
        generate_report(all_results, f"{prefix}_post_hyperopt.md")

    if phase in ("oos", "all"):
        if not all_results:
            all_results = phase_initial(strategies)
        all_results = phase_oos(all_results)
        generate_report(all_results, f"{prefix}_post_oos.md")

    if phase in ("regime", "all"):
        if not all_results:
            all_results = {}
        # Tester nouvelles + validees par regime
        all_strats = strategies + VALIDATED_STRATEGIES
        # Deduplicate (ADXRegimeFilter est dans les deux listes pour batch 2)
        all_strats = list(dict.fromkeys(all_strats))
        all_results = phase_regime(all_results, all_strats)
        generate_report(all_results, f"{prefix}_regime_report.md")

    # Rapport final
    if all_results:
        generate_report(all_results, f"{prefix}_final_report.md")

    print(f"\n{'=' * 60}")
    print("TERMINE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
