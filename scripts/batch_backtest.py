"""
Batch Backtest Runner v2 — Pipeline de validation quantitatif rigoureux.

Principes appliques:
- Separation stricte IS/OOS (zero chevauchement)
- Benchmark buy-and-hold
- Minimum 20 trades OOS pour significativite
- Sensitivity analysis (perturbation parametres)

Usage:
    python scripts/batch_backtest.py [--phase initial|hyperopt|oos|benchmark|sensitivity|regime|all] [--batch 1|2|3|revalidate]

Phases:
    initial     — Backtest IS (9 mois) pour toutes les strategies
    hyperopt    — Hyperopt 500 epochs sur IS uniquement
    oos         — Walk-forward OOS (3.5 mois, jamais vu par l'optimiseur)
    benchmark   — Calcul buy-and-hold pour comparaison
    sensitivity — Perturbation parametres ±1 step pour detecter overfitting
    regime      — Test par regime de marche
    all         — Toutes les phases sequentiellement
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

# Toutes les strategies validees (B0/B1/B2/B3) pour re-validation
ALL_VALIDATED = [
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
    "FibonacciPullback",
    "IchimokuBreakout",
    "BollingerMACDReversal",
    "KAMAAdaptiveTrend",
    "OBVTrendConfirm",
]

# Strategies Lite (simplifiees, 2 params) — validation finale
LITE_STRATEGIES = [
    "RSIDivergenceLite",
    "MACDDivergenceLite",
    "OBVDivergenceLite",
    "EMATripleCrossLite",
    "IchimokuBreakoutLite",
    "MARibbonStackLite",
    "DCASimple",
    # Phase 2 — 12 nouvelles Lite
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

# ── Periodes STRICTEMENT separees ──
IS_TIMERANGE = "20230101-20251130"    # ~35 mois — IN-SAMPLE (hyperopt + backtest initial)
OOS_TIMERANGE = "20251201-20260319"   # 3.5 mois — OUT-OF-SAMPLE (jamais vu par l'optimiseur)
FULL_TIMERANGE = "20230101-20260319"  # ~38 mois — reference seulement (pas pour hyperopt)

# Seuil minimum de trades OOS pour significativite statistique
MIN_OOS_TRADES = 20

# Regimes de marche hardcodes (fallback si auto-detection non disponible)
MARKET_REGIMES_HARDCODED = {
    "haussier": "20250301-20250601",
    "baissier": "20250601-20250901",
    "stable": "20250901-20251201",
    "full_12m": IS_TIMERANGE,
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
                regimes["full_12m"] = IS_TIMERANGE
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
    except subprocess.TimeoutExpired:
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


def run_hyperopt(strategy: str, epochs: int = 500) -> dict:
    """Lance un hyperopt sur IS uniquement et retourne les meilleurs params."""
    cmd = [
        "rtk", "freqtrade", "hyperopt",
        "--strategy", strategy,
        "-c", CONFIG,
        "--strategy-path", STRATEGY_PATH,
        "--timerange", IS_TIMERANGE,  # CORRECTION: hyperopt sur IS uniquement
        "--hyperopt-loss", "SharpeHyperOptLossDaily",
        "--epochs", str(epochs),
        "-j", "2",
    ]
    print(f"  Hyperopt {strategy} ({epochs} epochs, IS only)...", end=" ", flush=True)
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


# ── Buy-and-Hold Benchmark ──

def compute_buy_and_hold(timerange: str) -> dict:
    """Calcule le rendement buy-and-hold pour les 3 paires sur une periode.

    Utilise freqtrade list-data pour trouver les donnees OHLCV,
    puis calcule (close_fin - close_debut) / close_debut * 100.
    """
    print(f"\n  Calcul Buy & Hold [{timerange}]...")

    # Parse timerange
    parts = timerange.split("-")
    start_date = parts[0]
    end_date = parts[1]

    pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    returns = []

    for pair in pairs:
        # Utiliser freqtrade backtesting avec une strategie qui ne trade jamais
        # Plus simple: lancer un backtest et lire le prix de debut/fin dans les logs
        # Alternative: lire directement les fichiers OHLCV
        data_dir = PROJECT_ROOT / "user_data" / "data" / "binance"
        pair_file = pair.replace("/", "_")

        # Chercher le fichier OHLCV (format: BTC_USDT-4h.json ou .feather)
        candidates = list(data_dir.glob(f"{pair_file}-4h*"))
        if not candidates:
            print(f"    {pair}: fichier OHLCV non trouve, skip")
            continue

        data_file = candidates[0]
        try:
            if str(data_file).endswith(".json"):
                with open(data_file, encoding="utf-8") as f:
                    ohlcv = json.load(f)
                # Format: [[timestamp, open, high, low, close, volume], ...]
                # Filtrer par timerange
                from datetime import datetime as dt
                start_ts = int(dt.strptime(start_date, "%Y%m%d").timestamp() * 1000)
                end_ts = int(dt.strptime(end_date, "%Y%m%d").timestamp() * 1000)
                filtered = [c for c in ohlcv if start_ts <= c[0] <= end_ts]
                if len(filtered) < 2:
                    print(f"    {pair}: pas assez de donnees dans la periode")
                    continue
                close_start = filtered[0][4]
                close_end = filtered[-1][4]
            else:
                # Feather format — utiliser pandas
                import pandas as pd
                df = pd.read_feather(data_file)
                # Colonnes: date, open, high, low, close, volume
                date_col = "date" if "date" in df.columns else df.columns[0]
                df[date_col] = pd.to_datetime(df[date_col], utc=True)
                start_dt = pd.Timestamp(start_date, tz="UTC")
                end_dt = pd.Timestamp(end_date, tz="UTC")
                mask = (df[date_col] >= start_dt) & (df[date_col] <= end_dt)
                filtered = df[mask]
                if len(filtered) < 2:
                    print(f"    {pair}: pas assez de donnees dans la periode")
                    continue
                close_start = float(filtered.iloc[0]["close"])
                close_end = float(filtered.iloc[-1]["close"])

            ret = (close_end - close_start) / close_start * 100
            returns.append(ret)
            print(f"    {pair}: {close_start:.2f} → {close_end:.2f} = {ret:+.2f}%")

        except Exception as e:
            print(f"    {pair}: erreur lecture — {e}")
            continue

    if not returns:
        print("  Buy & Hold: impossible a calculer (pas de donnees)")
        return {"error": "no_data"}

    avg_return = sum(returns) / len(returns)
    print(f"  Buy & Hold moyen (equal weight): {avg_return:+.2f}%")
    return {
        "returns_by_pair": dict(zip([p.split("/")[0] for p in pairs[:len(returns)]], returns)),
        "avg_return_pct": avg_return,
    }


# ── Sensitivity Analysis ──

def sensitivity_test(strategy: str, timerange: str = IS_TIMERANGE) -> dict:
    """Perturbe les parametres hyperopt ±1 step et compare les resultats.

    Lit le fichier JSON de la strategie pour trouver les params optimaux,
    modifie chaque param ±1, relance un backtest IS, compare le profit.
    """
    json_file = Path(STRATEGY_PATH) / f"{strategy}.json"
    if not json_file.exists():
        print(f"  Sensitivity {strategy}: pas de fichier JSON, skip")
        return {"error": "no_json"}

    with open(json_file, encoding="utf-8") as f:
        params = json.load(f)

    # Extraire les params buy et sell
    buy_params = params.get("params", {}).get("buy", {})
    sell_params = params.get("params", {}).get("sell", {})
    all_params = {**buy_params, **sell_params}

    if not all_params:
        print(f"  Sensitivity {strategy}: aucun parametre, skip")
        return {"error": "no_params"}

    print(f"\n  Sensitivity {strategy} ({len(all_params)} params)...")

    # Backtest de reference avec params actuels
    ref_result = run_backtest(strategy, timerange)
    if "error" in ref_result:
        return {"error": "backtest_failed"}
    ref_profit = ref_result["tot_profit_pct"]

    # Pour chaque parametre, modifier ±1 et tester
    perturbations = []
    for param_name, value in all_params.items():
        if not isinstance(value, (int, float)):
            continue

        for delta_name, delta in [("-1", -1), ("+1", 1)]:
            new_value = value + delta
            # Sauvegarder le JSON original, modifier, backtest, restaurer
            original_params = params.copy()

            if param_name in buy_params:
                params.setdefault("params", {}).setdefault("buy", {})[param_name] = new_value
            else:
                params.setdefault("params", {}).setdefault("sell", {})[param_name] = new_value

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=2)

            perturbed = run_backtest(strategy, timerange)

            # Restaurer
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(original_params, f, indent=2)
            params = original_params

            if "error" not in perturbed:
                profit_delta = perturbed["tot_profit_pct"] - ref_profit
                perturbations.append({
                    "param": param_name,
                    "direction": delta_name,
                    "original": value,
                    "perturbed": new_value,
                    "ref_profit": ref_profit,
                    "new_profit": perturbed["tot_profit_pct"],
                    "delta_pct": profit_delta,
                })

    if not perturbations:
        return {"error": "no_perturbations"}

    # Calculer la fragilite: si une perturbation ±1 fait chuter le profit de > 50%
    max_drop = min(p["delta_pct"] for p in perturbations) if perturbations else 0
    avg_drop = sum(abs(p["delta_pct"]) for p in perturbations) / len(perturbations)
    fragile = ref_profit > 0 and max_drop < -(ref_profit * 0.5)

    result = {
        "ref_profit": ref_profit,
        "perturbations": perturbations,
        "max_drop_pct": max_drop,
        "avg_sensitivity": avg_drop,
        "fragile": fragile,
    }

    status = "FRAGILE" if fragile else "ROBUSTE"
    print(f"  → {status} (ref: {ref_profit:.2f}%, max drop: {max_drop:+.2f}%, avg sens: {avg_drop:.2f}%)")
    return result


# ── Classification ──

def classify_oos(result: dict, bh_return: float = 0.0) -> dict:
    """Classifie une strategie selon les criteres Tier + benchmark + significativite."""
    trades = result.get("trades", 0)
    profit = result.get("tot_profit_pct", 0)
    dd = result.get("drawdown_pct", 0)
    pf = result.get("profit_factor", 0)

    # PF=0.00 quand WR=100% (zero pertes) → traiter comme inf
    if pf == 0.0 and result.get("win_rate", 0) == 100.0 and trades > 0:
        pf = 999

    classification = {
        "tier": "ECHEC",
        "significant": trades >= MIN_OOS_TRADES,
        "beats_bh": profit > bh_return,
        "pf_adjusted": pf,
    }

    # Echec si profit <= 0 OU DD > 25% OU PF < 1.0
    if profit <= 0 or dd > 25 or (pf < 1.0 and pf != 999):
        classification["tier"] = "ECHEC"
    elif profit >= 17.5 and dd < 15 and pf >= 2.0:
        classification["tier"] = "TIER 1"
    elif profit >= 10.5 and dd < 20 and pf >= 1.5:
        classification["tier"] = "TIER 2"
    elif profit > 0 and dd < 25 and pf > 1.0:
        classification["tier"] = "TIER 3"

    # Downgrade si non significatif
    if not classification["significant"] and classification["tier"] != "ECHEC":
        classification["tier"] += " (NS)"  # Non Significatif

    # Flag si ne bat pas le buy-and-hold
    if not classification["beats_bh"] and classification["tier"] != "ECHEC":
        classification["tier"] += " (!BH)"

    return classification


# ── Report Generation ──

def generate_report(all_results: dict, filename: str = "report.md",
                    bh_data: dict | None = None,
                    sensitivity_data: dict | None = None) -> None:
    """Genere un rapport markdown avec resultats, benchmark, significativite."""
    report_path = REPORTS_DIR / filename
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Rapport — {timestamp}",
        "",
        "## Parametres de validation",
        f"- IS (In-Sample): {IS_TIMERANGE} (9 mois — hyperopt)",
        f"- OOS (Out-of-Sample): {OOS_TIMERANGE} (3.5 mois — validation)",
        f"- Min trades OOS: {MIN_OOS_TRADES}",
        "",
    ]

    # Buy-and-hold benchmark
    if bh_data and "avg_return_pct" in bh_data:
        lines.append(f"## Benchmark Buy & Hold (OOS)")
        lines.append(f"- Rendement moyen (equal weight): **{bh_data['avg_return_pct']:+.2f}%**")
        if "returns_by_pair" in bh_data:
            for pair, ret in bh_data["returns_by_pair"].items():
                lines.append(f"  - {pair}/USDT: {ret:+.2f}%")
        lines.append("")

    # Resultats par strategie
    lines.append("## Resultats par strategie et regime")
    lines.append("")
    lines.append("| Strategie | Regime | Trades | Profit% | DD% | WR% | PF | Sharpe | Expectancy | ConsecLoss |")
    lines.append("|-----------|--------|--------|---------|-----|-----|-----|--------|------------|------------|")

    for strategy, regimes in sorted(all_results.items()):
        for regime, result in sorted(regimes.items()):
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

    # Classement IS
    lines.extend(["", "## Classement IS (trie par profit)", ""])
    is_results = []
    for strategy, regimes in all_results.items():
        # Chercher le backtest IS (peut etre sous differents noms)
        for key in ("is_9m", "full_12m", "full_12m_post_hyperopt"):
            if key in regimes and isinstance(regimes[key], dict) and "trades" in regimes[key]:
                is_results.append((strategy, regimes[key]))
                break

    is_results.sort(key=lambda x: x[1]["tot_profit_pct"], reverse=True)
    lines.append("| # | Strategie | Profit% | DD% | WR% | PF | Sharpe | Trades |")
    lines.append("|---|-----------|---------|-----|-----|-----|--------|--------|")
    for i, (strat, r) in enumerate(is_results, 1):
        lines.append(
            f"| {i} | {strat} | {r['tot_profit_pct']:.2f} | "
            f"{r['drawdown_pct']:.2f} | {r['win_rate']:.1f} | "
            f"{r['profit_factor']:.2f} | {r['sharpe']:.2f} | {r['trades']} |"
        )

    # Classification OOS
    bh_return = bh_data.get("avg_return_pct", 0.0) if bh_data else 0.0
    oos_results = []
    for strategy, regimes in all_results.items():
        if "oos" in regimes and isinstance(regimes["oos"], dict) and "trades" in regimes["oos"]:
            cls = classify_oos(regimes["oos"], bh_return)
            oos_results.append((strategy, regimes["oos"], cls))

    if oos_results:
        oos_results.sort(key=lambda x: x[1]["tot_profit_pct"], reverse=True)
        lines.extend(["", "## Validation OOS (classification)", ""])
        lines.append(f"- Benchmark B&H: {bh_return:+.2f}%")
        lines.append(f"- Min trades: {MIN_OOS_TRADES}")
        lines.append("")
        lines.append("| # | Strategie | Profit% | DD% | WR% | PF | Trades | Tier | Significatif | > B&H |")
        lines.append("|---|-----------|---------|-----|-----|-----|--------|------|-------------|-------|")
        for i, (strat, r, cls) in enumerate(oos_results, 1):
            pf_display = cls["pf_adjusted"]
            pf_str = "999*" if pf_display == 999 else f"{pf_display:.2f}"
            sig = "OUI" if cls["significant"] else "NON"
            bh = "OUI" if cls["beats_bh"] else "NON"
            lines.append(
                f"| {i} | {strat} | {r['tot_profit_pct']:+.2f} | "
                f"{r['drawdown_pct']:.2f} | {r['win_rate']:.1f} | "
                f"{pf_str} | {r['trades']} | **{cls['tier']}** | {sig} | {bh} |"
            )

    # Sensitivity results
    if sensitivity_data:
        lines.extend(["", "## Sensitivity Analysis (robustesse des parametres)", ""])
        lines.append("| Strategie | Profit ref% | Max drop% | Avg sensitivity | Status |")
        lines.append("|-----------|------------|-----------|----------------|--------|")
        for strat, sens in sorted(sensitivity_data.items()):
            if "error" in sens:
                lines.append(f"| {strat} | — | — | — | {sens['error']} |")
            else:
                status = "FRAGILE" if sens["fragile"] else "ROBUSTE"
                lines.append(
                    f"| {strat} | {sens['ref_profit']:.2f} | "
                    f"{sens['max_drop_pct']:+.2f} | {sens['avg_sensitivity']:.2f} | **{status}** |"
                )

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


# ── Phases ──

def phase_initial(strategies: list[str]) -> dict:
    """Phase 1: Backtest IS (9 mois) pour toutes les strategies."""
    print("\n" + "=" * 60)
    print(f"PHASE 1 — BACKTESTS INITIAUX IS ({IS_TIMERANGE})")
    print("=" * 60)

    results = {}
    for strat in strategies:
        results[strat] = {"is_9m": run_backtest(strat, IS_TIMERANGE)}
    return results


def phase_hyperopt(results: dict, hyperopt_all: bool = True) -> dict:
    """Phase 2: Hyperopt 500 epochs sur IS uniquement."""
    print("\n" + "=" * 60)
    print(f"PHASE 2 — HYPEROPT (500 epochs, IS only: {IS_TIMERANGE})")
    print("=" * 60)

    if hyperopt_all:
        to_hyperopt = list(results.keys())
        print(f"  Mode TOUTES : {len(to_hyperopt)} strategies")
    else:
        to_hyperopt = [
            s for s, r in results.items()
            if "is_9m" in r
            and isinstance(r["is_9m"], dict)
            and "trades" in r["is_9m"]
            and r["is_9m"]["tot_profit_pct"] > 0
        ]
        if not to_hyperopt:
            print("  Aucune strategie rentable, skip hyperopt.")
            return results
        print(f"  Strategies rentables: {', '.join(to_hyperopt)}")

    for strat in to_hyperopt:
        hyperopt_result = run_hyperopt(strat, epochs=500)
        results[strat]["hyperopt"] = hyperopt_result

        # Re-backtest IS apres hyperopt
        if "error" not in hyperopt_result:
            results[strat]["is_9m_post_hyperopt"] = run_backtest(strat, IS_TIMERANGE)

    return results


def phase_oos(results: dict) -> dict:
    """Phase 3: Walk-forward OOS — JAMAIS vu par l'optimiseur."""
    print("\n" + "=" * 60)
    print(f"PHASE 3 — WALK-FORWARD OOS ({OOS_TIMERANGE})")
    print("=" * 60)

    for strat in list(results.keys()):
        # Tester toutes les strategies (meme sans hyperopt, pour avoir la baseline)
        results[strat]["oos"] = run_backtest(strat, OOS_TIMERANGE)

    return results


def phase_benchmark() -> dict:
    """Phase 4: Benchmark buy-and-hold."""
    print("\n" + "=" * 60)
    print("PHASE 4 — BENCHMARK BUY & HOLD")
    print("=" * 60)
    return compute_buy_and_hold(OOS_TIMERANGE)


def phase_sensitivity(results: dict) -> dict:
    """Phase 5: Sensitivity analysis pour les strategies validees OOS."""
    print("\n" + "=" * 60)
    print("PHASE 5 — SENSITIVITY ANALYSIS")
    print("=" * 60)

    sensitivity_results = {}
    for strat in results:
        oos = results[strat].get("oos", {})
        if isinstance(oos, dict) and "trades" in oos and oos.get("tot_profit_pct", 0) > 0:
            sensitivity_results[strat] = sensitivity_test(strat, IS_TIMERANGE)

    return sensitivity_results


def phase_regime(results: dict, strategies: list[str]) -> dict:
    """Phase 6: Test par regime de marche."""
    print("\n" + "=" * 60)
    print("PHASE 6 — TESTS PAR REGIME DE MARCHE")
    print("=" * 60)

    for strat in strategies:
        if strat not in results:
            results[strat] = {}
        for regime_name, timerange in MARKET_REGIMES.items():
            if regime_name == "full_12m" and "is_9m" in results.get(strat, {}):
                continue
            results[strat][regime_name] = run_backtest(strat, timerange)

    return results


# ── Main ──

def parse_args() -> tuple:
    """Parse les arguments CLI."""
    phase = "all"
    batch = "revalidate"

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
            batch = args[i + 1]
            i += 2
        elif args[i].startswith("--batch="):
            batch = args[i].split("=")[1]
            i += 1
        else:
            phase = args[i]
            i += 1

    return phase, batch


def main():
    phase, batch = parse_args()

    print(f"\n{'=' * 60}")
    print(f"BATCH {batch} — Phase: {phase}")
    print(f"IS: {IS_TIMERANGE} | OOS: {OOS_TIMERANGE}")
    print(f"Min trades OOS: {MIN_OOS_TRADES}")
    print(f"{'=' * 60}")

    if batch == "lite":
        strategies = LITE_STRATEGIES
        hyperopt_all = True
        prefix = "lite_validation"
    elif batch == "revalidate":
        strategies = ALL_VALIDATED
        hyperopt_all = True
        prefix = "revalidation"
    elif batch == "3":
        strategies = BATCH_3_STRATEGIES
        hyperopt_all = True
        prefix = "batch3"
    elif batch == "2":
        strategies = BATCH_2_STRATEGIES
        hyperopt_all = True
        prefix = "batch2"
    else:
        strategies = BATCH_1_STRATEGIES
        hyperopt_all = False
        prefix = "batch1"

    all_results = {}
    bh_data = None
    sensitivity_data = None

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
            # Si on lance OOS seul, on fait juste le backtest OOS
            all_results = {s: {} for s in strategies}
        all_results = phase_oos(all_results)
        generate_report(all_results, f"{prefix}_post_oos.md")

    if phase in ("benchmark", "all"):
        bh_data = phase_benchmark()

    if phase in ("sensitivity", "all"):
        if not all_results:
            all_results = {s: {} for s in strategies}
            all_results = phase_oos(all_results)
        sensitivity_data = phase_sensitivity(all_results)

    if phase in ("regime", "all"):
        if not all_results:
            all_results = {}
        all_results = phase_regime(all_results, strategies)

    # Rapport final
    if all_results:
        generate_report(all_results, f"{prefix}_final_report.md",
                        bh_data=bh_data, sensitivity_data=sensitivity_data)

    print(f"\n{'=' * 60}")
    print("TERMINE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
