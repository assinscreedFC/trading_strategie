#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT : detect_regimes.py
# ROLE   : Detection automatique des regimes de marche via ADX + EMA
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Analyse BTC/USDT 1d pour classifier chaque jour en regime :
# - ADX(14) > 25 + EMA(50) monte → HAUSSIER
# - ADX(14) > 25 + EMA(50) descend → BAISSIER
# - ADX(14) < 20 → STABLE/RANGE
# - ADX(14) 20-25 → TRANSITION (zone grise)
#
# Seuils de Wilder (createur ADX) : 20/25 sont les standards.
# Direction EMA : comparaison EMA(50) actuelle vs 5 jours avant.
# ══════════════════════════════════════════════════════════════

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.indicators import CommonIndicators

# ── Configuration ──
DATA_PATH = Path(__file__).resolve().parent.parent / "user_data" / "data" / "binance"
BTC_FILE = DATA_PATH / "BTC_USDT-1d.feather"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "reports" / "detected_regimes.json"

ADX_PERIOD = 14
EMA_PERIOD = 50
EMA_DIRECTION_LOOKBACK = 5  # Comparer EMA vs 5 jours avant
ADX_TREND_THRESHOLD = 25
ADX_RANGE_THRESHOLD = 20
MIN_REGIME_DAYS = 20  # Periodes < 20 jours = bruit


def load_btc_data() -> pd.DataFrame:
    """Charge les donnees BTC 1d depuis le feather."""
    if not BTC_FILE.exists():
        # Essayer les formats alternatifs
        alt_files = list(DATA_PATH.glob("BTC_USDT*.feather")) + list(DATA_PATH.glob("BTC_USDT*.json"))
        if alt_files:
            file = alt_files[0]
            print(f"Fichier principal non trouve, utilisation de : {file.name}")
            if file.suffix == ".feather":
                return pd.read_feather(file)
            return pd.read_json(file)
        raise FileNotFoundError(f"Aucune donnee BTC trouvee dans {DATA_PATH}")

    return pd.read_feather(BTC_FILE)


def classify_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """Classifie chaque bougie en regime de marche."""
    df = CommonIndicators.add_adx(df, period=ADX_PERIOD)
    df = CommonIndicators.add_ema(df, period=EMA_PERIOD)

    adx_col = f"adx_{ADX_PERIOD}"
    ema_col = f"ema_{EMA_PERIOD}"

    # Direction EMA : monte si EMA actuelle > EMA il y a N jours
    ema_rising = df[ema_col] > df[ema_col].shift(EMA_DIRECTION_LOOKBACK)

    # Classification
    conditions = []
    regimes = []

    # HAUSSIER : ADX > 25 + EMA monte
    bull = (df[adx_col] > ADX_TREND_THRESHOLD) & ema_rising
    conditions.append(bull)
    regimes.append("haussier")

    # BAISSIER : ADX > 25 + EMA descend
    bear = (df[adx_col] > ADX_TREND_THRESHOLD) & ~ema_rising
    conditions.append(bear)
    regimes.append("baissier")

    # STABLE : ADX < 20
    stable = df[adx_col] < ADX_RANGE_THRESHOLD
    conditions.append(stable)
    regimes.append("stable")

    # TRANSITION : ADX 20-25 (zone grise)
    transition = (df[adx_col] >= ADX_RANGE_THRESHOLD) & (df[adx_col] <= ADX_TREND_THRESHOLD)
    conditions.append(transition)
    regimes.append("transition")

    # Appliquer la classification (priorite : bull > bear > stable > transition)
    df["regime"] = "transition"
    for cond, regime in reversed(list(zip(conditions, regimes))):
        df.loc[cond, "regime"] = regime

    return df


def merge_consecutive_periods(df: pd.DataFrame) -> dict:
    """Fusionne les jours consecutifs du meme regime en periodes."""
    result = {"haussier": [], "baissier": [], "stable": [], "transition": []}

    if df.empty:
        return result

    # Identifier les changements de regime
    df = df.copy()
    df["regime_change"] = df["regime"] != df["regime"].shift(1)
    df["group_id"] = df["regime_change"].cumsum()

    for _, group in df.groupby("group_id"):
        regime = group["regime"].iloc[0]
        start_date = group["date"].iloc[0] if "date" in group.columns else group.index[0]
        end_date = group["date"].iloc[-1] if "date" in group.columns else group.index[-1]

        # Convertir en string format YYYYMMDD
        if isinstance(start_date, pd.Timestamp):
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
        else:
            start_str = str(start_date).replace("-", "")[:8]
            end_str = str(end_date).replace("-", "")[:8]

        duration = len(group)

        result[regime].append({
            "start": start_str,
            "end": end_str,
            "duration_days": duration,
        })

    return result


def filter_short_periods(regimes: dict, min_days: int = MIN_REGIME_DAYS) -> dict:
    """Filtre les periodes trop courtes (bruit statistique)."""
    filtered = {}
    for regime, periods in regimes.items():
        filtered[regime] = [p for p in periods if p["duration_days"] >= min_days]
    return filtered


def select_longest_per_regime(regimes: dict) -> dict:
    """Selectionne la periode la plus longue par regime pour les backtests."""
    selected = {}
    for regime, periods in regimes.items():
        if not periods:
            continue
        longest = max(periods, key=lambda p: p["duration_days"])
        selected[regime] = f"{longest['start']}-{longest['end']}"
    return selected


def print_summary(all_regimes: dict, filtered: dict, selected: dict) -> None:
    """Affiche un resume lisible des regimes detectes."""
    print("\n" + "=" * 60)
    print("DETECTION AUTOMATIQUE DES REGIMES DE MARCHE")
    print("Methode : ADX(14) + Direction EMA(50)")
    print("=" * 60)

    for regime in ["haussier", "baissier", "stable", "transition"]:
        all_count = len(all_regimes.get(regime, []))
        filt_count = len(filtered.get(regime, []))
        print(f"\n{'─' * 40}")
        print(f"REGIME : {regime.upper()}")
        print(f"Periodes totales : {all_count} | Apres filtre (>{MIN_REGIME_DAYS}j) : {filt_count}")

        for p in filtered.get(regime, []):
            print(f"  {p['start']}-{p['end']} ({p['duration_days']} jours)")

    print(f"\n{'─' * 40}")
    print("PERIODES SELECTIONNEES POUR BACKTESTS :")
    for regime, timerange in selected.items():
        if regime != "transition":
            print(f"  {regime:10s} : {timerange}")
    print("=" * 60)


def main():
    print("Chargement des donnees BTC/USDT 1d...")
    df = load_btc_data()

    # Normaliser la colonne date
    if "date" not in df.columns:
        date_candidates = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
        if date_candidates:
            df["date"] = pd.to_datetime(df[date_candidates[0]])
        elif isinstance(df.index, pd.DatetimeIndex):
            df["date"] = df.index
        else:
            raise ValueError("Pas de colonne date trouvee dans les donnees")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    print(f"Periode : {df['date'].iloc[0].strftime('%Y-%m-%d')} → {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"Bougies : {len(df)}")

    # Classifier
    print("Classification des regimes...")
    df = classify_regimes(df)

    # Resume rapide
    regime_counts = df["regime"].value_counts()
    for regime, count in regime_counts.items():
        pct = 100 * count / len(df)
        print(f"  {regime:12s} : {count:4d} jours ({pct:.1f}%)")

    # Fusionner et filtrer
    all_regimes = merge_consecutive_periods(df)
    filtered = filter_short_periods(all_regimes)
    selected = select_longest_per_regime(filtered)

    # Afficher
    print_summary(all_regimes, filtered, selected)

    # Sauvegarder
    output = {
        "method": "ADX(14) + EMA(50) direction",
        "thresholds": {
            "adx_trend": ADX_TREND_THRESHOLD,
            "adx_range": ADX_RANGE_THRESHOLD,
            "ema_direction_lookback": EMA_DIRECTION_LOOKBACK,
            "min_regime_days": MIN_REGIME_DAYS,
        },
        "generated_at": datetime.now().isoformat(),
        "all_periods": all_regimes,
        "filtered_periods": filtered,
        "selected_timeranges": selected,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResultats sauvegardes dans : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
