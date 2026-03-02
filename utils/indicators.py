# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# MODULE : indicators.py
# RÔLE  : Indicateurs techniques PARTAGÉS entre toutes les stratégies
# ══════════════════════════════════════════════════════════════
#
# ARCHITECTURE DE REFACTORING :
# → Tous les calculs d'indicateurs techniques réutilisés par
#   plusieurs stratégies sont centralisés ICI.
# → Les stratégies Freqtrade appellent ces fonctions dans leur
#   populate_indicators() au lieu de recoder les calculs.
#
# POURQUOI :
# - GridTrading, MeanReversion et DCA utilisent tous le RSI
# - TrendFollowing et MultiFactorCorrelation utilisent les EMA
# - Plusieurs stratégies utilisent ATR, Bollinger Bands, Volume
# → Sans refactoring, chaque fichier recoderait les mêmes lignes
#
# USAGE :
#   from utils.indicators import CommonIndicators
#   CommonIndicators.add_rsi(dataframe, period=14)
#   CommonIndicators.add_bollinger_bands(dataframe, period=20, std=2.0)
# ══════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from typing import Optional

try:
    import pandas_ta as pta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


class CommonIndicators:
    """
    Bibliothèque d'indicateurs techniques partagés.

    PRINCIPE DE REFACTORING :
    Chaque méthode ajoute une ou plusieurs colonnes au DataFrame.
    Les noms de colonnes suivent la convention : {indicateur}_{période}
    (ex: rsi_14, ema_50, bb_upper_20)

    COMPATIBILITÉ :
    - Utilise pandas-ta si disponible (recommandé)
    - Fallback sur calcul manuel si pandas-ta n'est pas installé
    - Supporte aussi TA-Lib si disponible
    """

    # ══════════════════════════════════════════════════════════
    # RSI — Utilisé par : GridTrading, DCA, MeanReversion
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_rsi(
        df: pd.DataFrame,
        period: int = 14,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute le RSI (Relative Strength Index) au DataFrame.

        CHOIX : La méthode Wilder (lissage exponentiel) est utilisée
        car c'est le standard en trading crypto. pandas-ta l'implémente
        correctement, contrairement à certains calculs manuels qui
        utilisent un SMA au lieu d'un EMA.

        Colonne ajoutée : rsi_{period} (ex: rsi_14)
        """
        col_name = f"rsi_{period}"
        if HAS_PANDAS_TA:
            df[col_name] = pta.rsi(df[column], length=period)
        else:
            # Fallback : calcul manuel (méthode Wilder)
            delta = df[column].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
            avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            df[col_name] = 100 - (100 / (1 + rs))
        return df

    # ══════════════════════════════════════════════════════════
    # EMA — Utilisé par : TrendFollowing, MultiFactorCorrelation
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_ema(
        df: pd.DataFrame,
        period: int = 50,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute une EMA (Exponential Moving Average) au DataFrame.

        CHOIX : EMA plutôt que SMA car elle réagit plus vite aux
        changements de prix, ce qui est crucial en crypto.

        Colonne ajoutée : ema_{period} (ex: ema_50)
        """
        col_name = f"ema_{period}"
        if HAS_PANDAS_TA:
            df[col_name] = pta.ema(df[column], length=period)
        else:
            df[col_name] = df[column].ewm(span=period, adjust=False).mean()
        return df

    # ══════════════════════════════════════════════════════════
    # Bollinger Bands — Utilisé par : MeanReversion
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_bollinger_bands(
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute les Bollinger Bands au DataFrame.

        CHOIX DU STD_DEV :
        - 2.0σ est le standard pour la mean reversion
        - Configurable pour adapter à la volatilité crypto (souvent 2.5σ)

        Colonnes ajoutées : bb_upper_{period}, bb_middle_{period}, bb_lower_{period}
        """
        prefix = f"bb"
        if HAS_PANDAS_TA:
            bb = pta.bbands(df[column], length=period, std=std_dev)
            if bb is not None:
                df[f"{prefix}_lower_{period}"] = bb.iloc[:, 0]
                df[f"{prefix}_middle_{period}"] = bb.iloc[:, 1]
                df[f"{prefix}_upper_{period}"] = bb.iloc[:, 2]
        else:
            # Fallback manuel
            sma = df[column].rolling(window=period).mean()
            std = df[column].rolling(window=period).std()
            df[f"{prefix}_upper_{period}"] = sma + (std_dev * std)
            df[f"{prefix}_middle_{period}"] = sma
            df[f"{prefix}_lower_{period}"] = sma - (std_dev * std)
        return df

    # ══════════════════════════════════════════════════════════
    # ATR — Utilisé par : GridTrading, TrendFollowing
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_atr(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """
        Ajoute l'ATR (Average True Range) pour mesurer la volatilité.

        CHOIX : Utilisé pour adapter dynamiquement :
        - L'espacement du grid (GridTrading)
        - La taille du trailing stop (TrendFollowing)

        Colonne ajoutée : atr_{period}
        """
        col_name = f"atr_{period}"
        if HAS_PANDAS_TA:
            df[col_name] = pta.atr(df["high"], df["low"], df["close"], length=period)
        else:
            high_low = df["high"] - df["low"]
            high_close = (df["high"] - df["close"].shift()).abs()
            low_close = (df["low"] - df["close"].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df[col_name] = tr.ewm(alpha=1/period, min_periods=period).mean()
        return df

    # ══════════════════════════════════════════════════════════
    # ADX — Utilisé par : TrendFollowing
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_adx(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """
        Ajoute l'ADX (Average Directional Index) pour force de tendance.

        CHOIX : Un ADX > 25 indique une tendance suffisamment forte
        pour le Trend Following. Valeur configurable dans la stratégie.

        Colonne ajoutée : adx_{period}
        """
        col_name = f"adx_{period}"
        if HAS_PANDAS_TA:
            adx_data = pta.adx(df["high"], df["low"], df["close"], length=period)
            if adx_data is not None:
                df[col_name] = adx_data.iloc[:, 0]  # ADX column
        else:
            # Fallback simplifié
            plus_dm = df["high"].diff().clip(lower=0)
            minus_dm = (-df["low"].diff()).clip(lower=0)
            atr_col = f"atr_{period}"
            if atr_col not in df.columns:
                CommonIndicators.add_atr(df, period)
            plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / df[atr_col])
            minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / df[atr_col])
            dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
            df[col_name] = dx.ewm(alpha=1/period).mean()
        return df

    # ══════════════════════════════════════════════════════════
    # Volume — Utilisé par : TrendFollowing, MeanReversion
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_volume_sma(
        df: pd.DataFrame,
        period: int = 20,
    ) -> pd.DataFrame:
        """
        Ajoute la moyenne mobile du volume.

        UTILISATION : Détecter les spikes de volume qui confirment
        les breakouts (TrendFollowing) ou les déviations extrêmes (MeanReversion).

        Colonnes ajoutées : volume_sma_{period}, volume_ratio_{period}
        """
        sma_name = f"volume_sma_{period}"
        ratio_name = f"volume_ratio_{period}"
        df[sma_name] = df["volume"].rolling(window=period).mean()
        df[ratio_name] = df["volume"] / df[sma_name]
        return df

    # ══════════════════════════════════════════════════════════
    # Breakout Detection — Utilisé par : TrendFollowing
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_breakout_levels(
        df: pd.DataFrame,
        period: int = 20,
    ) -> pd.DataFrame:
        """
        Ajoute les niveaux de breakout (plus haut et plus bas sur N périodes).

        Colonnes ajoutées : breakout_high_{period}, breakout_low_{period}
        """
        df[f"breakout_high_{period}"] = df["high"].rolling(window=period).max()
        df[f"breakout_low_{period}"] = df["low"].rolling(window=period).min()
        return df

    # ══════════════════════════════════════════════════════════
    # MACD — Utilisé par : MultiFactorCorrelation
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_macd(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute le MACD (Moving Average Convergence Divergence).

        Colonnes ajoutées : macd, macd_signal, macd_histogram
        """
        if HAS_PANDAS_TA:
            macd_data = pta.macd(df[column], fast=fast, slow=slow, signal=signal)
            if macd_data is not None:
                df["macd"] = macd_data.iloc[:, 0]
                df["macd_histogram"] = macd_data.iloc[:, 1]
                df["macd_signal"] = macd_data.iloc[:, 2]
        else:
            ema_fast = df[column].ewm(span=fast, adjust=False).mean()
            ema_slow = df[column].ewm(span=slow, adjust=False).mean()
            df["macd"] = ema_fast - ema_slow
            df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
            df["macd_histogram"] = df["macd"] - df["macd_signal"]
        return df

    # ══════════════════════════════════════════════════════════
    # Méthode utilitaire : Ajouter TOUS les indicateurs de base
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_all_basic(
        df: pd.DataFrame,
        rsi_period: int = 14,
        ema_periods: Optional[list[int]] = None,
        bb_period: int = 20,
        bb_std: float = 2.0,
        atr_period: int = 14,
        volume_period: int = 20,
    ) -> pd.DataFrame:
        """
        Ajoute tous les indicateurs de base en un seul appel.

        Pratique pour les stratégies qui utilisent plusieurs indicateurs.
        Chaque indicateur est ajouté avec des paramètres configurables.
        """
        if ema_periods is None:
            ema_periods = [50, 200]

        df = CommonIndicators.add_rsi(df, period=rsi_period)
        for period in ema_periods:
            df = CommonIndicators.add_ema(df, period=period)
        df = CommonIndicators.add_bollinger_bands(df, period=bb_period, std_dev=bb_std)
        df = CommonIndicators.add_atr(df, period=atr_period)
        df = CommonIndicators.add_volume_sma(df, period=volume_period)
        return df
