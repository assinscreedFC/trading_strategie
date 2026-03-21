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

    # ══════════════════════════════════════════════════════════
    # SMA — Utilisé par : RSI2Connors, CumulativeRSI (filtre trend)
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_sma(
        df: pd.DataFrame,
        period: int = 200,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute une SMA (Simple Moving Average) au DataFrame.
        Colonne ajoutée : sma_{period}
        """
        col_name = f"sma_{period}"
        df[col_name] = df[column].rolling(window=period).mean()
        return df

    # ══════════════════════════════════════════════════════════
    # ADOSC — Utilisé par : ADOSCTrailing
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_adosc(
        df: pd.DataFrame,
        fast: int = 3,
        slow: int = 10,
    ) -> pd.DataFrame:
        """
        Ajoute l'ADOSC (Accumulation/Distribution Oscillator).
        C'est l'oscillateur de la ligne AD (différence EMA rapide - EMA lente de AD).
        Colonne ajoutée : adosc_{fast}_{slow}
        """
        col_name = f"adosc_{fast}_{slow}"
        if HAS_TALIB:
            df[col_name] = talib.ADOSC(df["high"], df["low"], df["close"], df["volume"],
                                        fastperiod=fast, slowperiod=slow)
        else:
            # Calcul manuel : AD line puis oscillateur
            clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"]).replace(0, np.nan)
            clv = clv.fillna(0)
            ad_line = (clv * df["volume"]).cumsum()
            ema_fast = ad_line.ewm(span=fast, adjust=False).mean()
            ema_slow = ad_line.ewm(span=slow, adjust=False).mean()
            df[col_name] = ema_fast - ema_slow
        return df

    # ══════════════════════════════════════════════════════════
    # VWMA — Utilisé par : VWMASMACross
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_vwma(
        df: pd.DataFrame,
        period: int = 20,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        Ajoute la VWMA (Volume Weighted Moving Average).
        VWMA = SUM(close * volume, period) / SUM(volume, period)
        Colonne ajoutée : vwma_{period}
        """
        col_name = f"vwma_{period}"
        if HAS_PANDAS_TA:
            result = pta.vwma(df[column], df["volume"], length=period)
            if result is not None:
                df[col_name] = result
            else:
                df[col_name] = (df[column] * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()
        else:
            df[col_name] = (df[column] * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()
        return df

    # ══════════════════════════════════════════════════════════
    # Stochastic — Utilisé par : StochasticMomentumIndex
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_stochastic(
        df: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3,
    ) -> pd.DataFrame:
        """
        Ajoute le Stochastic Oscillator (%K et %D).
        %K = (close - lowest_low) / (highest_high - lowest_low) * 100
        %D = SMA(%K, d_period)
        Colonnes ajoutées : stoch_k_{k_period}, stoch_d_{k_period}
        """
        k_col = f"stoch_k_{k_period}"
        d_col = f"stoch_d_{k_period}"
        if HAS_PANDAS_TA:
            stoch = pta.stoch(df["high"], df["low"], df["close"], k=k_period, d=d_period)
            if stoch is not None:
                df[k_col] = stoch.iloc[:, 0]
                df[d_col] = stoch.iloc[:, 1]
            else:
                lowest = df["low"].rolling(window=k_period).min()
                highest = df["high"].rolling(window=k_period).max()
                df[k_col] = 100 * (df["close"] - lowest) / (highest - lowest).replace(0, np.nan)
                df[d_col] = df[k_col].rolling(window=d_period).mean()
        else:
            lowest = df["low"].rolling(window=k_period).min()
            highest = df["high"].rolling(window=k_period).max()
            df[k_col] = 100 * (df["close"] - lowest) / (highest - lowest).replace(0, np.nan)
            df[d_col] = df[k_col].rolling(window=d_period).mean()
        return df

    # ══════════════════════════════════════════════════════════
    # Keltner Channels — Utilisé par : KeltnerChannelMomentum
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_keltner_channels(
        df: pd.DataFrame,
        period: int = 20,
        atr_mult: float = 1.5,
    ) -> pd.DataFrame:
        """
        Ajoute les Keltner Channels (EMA ± ATR * multiplicateur).
        Basé sur ATR (volatilité réelle) vs Bollinger qui utilise std dev.
        Colonnes ajoutées : keltner_upper_{period}, keltner_middle_{period}, keltner_lower_{period}
        """
        ema_col = f"ema_{period}"
        atr_col = f"atr_{period}"
        if ema_col not in df.columns:
            CommonIndicators.add_ema(df, period=period)
        if atr_col not in df.columns:
            CommonIndicators.add_atr(df, period=period)
        df[f"keltner_upper_{period}"] = df[ema_col] + atr_mult * df[atr_col]
        df[f"keltner_middle_{period}"] = df[ema_col]
        df[f"keltner_lower_{period}"] = df[ema_col] - atr_mult * df[atr_col]
        return df

    # ══════════════════════════════════════════════════════════
    # Choppiness Index — Utilisé par : ChoppinessBreakout
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_choppiness(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """
        Ajoute le Choppiness Index.
        CI = 100 * LOG10(SUM(ATR, period) / (highest_high - lowest_low)) / LOG10(period)
        Valeurs : 0-100. > 61.8 = choppy, < 38.2 = trending.
        Colonne ajoutée : choppiness_{period}
        """
        col_name = f"choppiness_{period}"
        atr_col = f"atr_{period}"
        if atr_col not in df.columns:
            CommonIndicators.add_atr(df, period=period)
        atr_sum = df[atr_col].rolling(window=period).sum()
        highest = df["high"].rolling(window=period).max()
        lowest = df["low"].rolling(window=period).min()
        hl_range = (highest - lowest).replace(0, np.nan)
        df[col_name] = 100 * np.log10(atr_sum / hl_range) / np.log10(period)
        return df

    # ══════════════════════════════════════════════════════════
    # MFI — Utilisé par : MoneyFlowIndex
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_mfi(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """
        Ajoute le Money Flow Index (RSI pondéré par volume).
        MFI combine prix et volume pour détecter la pression acheteuse/vendeuse.
        Colonne ajoutée : mfi_{period}
        """
        col_name = f"mfi_{period}"
        if HAS_PANDAS_TA:
            result = pta.mfi(df["high"], df["low"], df["close"], df["volume"], length=period)
            if result is not None:
                df[col_name] = result
            else:
                df = CommonIndicators._mfi_manual(df, period, col_name)
        else:
            df = CommonIndicators._mfi_manual(df, period, col_name)
        return df

    @staticmethod
    def _mfi_manual(df: pd.DataFrame, period: int, col_name: str) -> pd.DataFrame:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        raw_money_flow = typical_price * df["volume"]
        tp_diff = typical_price.diff()
        pos_flow = raw_money_flow.where(tp_diff > 0, 0.0).rolling(window=period).sum()
        neg_flow = raw_money_flow.where(tp_diff < 0, 0.0).rolling(window=period).sum()
        money_ratio = pos_flow / neg_flow.replace(0, np.nan)
        df[col_name] = 100 - (100 / (1 + money_ratio))
        return df

    # ══════════════════════════════════════════════════════════
    # DMI (+DI / -DI) — Utilisé par : DMICrossover
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_dmi(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.DataFrame:
        """
        Ajoute +DI et -DI (Directional Movement Indicators).
        Complémente add_adx() qui ne retourne que l'ADX.
        Colonnes ajoutées : plus_di_{period}, minus_di_{period}
        """
        plus_col = f"plus_di_{period}"
        minus_col = f"minus_di_{period}"
        if HAS_PANDAS_TA:
            adx_data = pta.adx(df["high"], df["low"], df["close"], length=period)
            if adx_data is not None and adx_data.shape[1] >= 3:
                df[plus_col] = adx_data.iloc[:, 1]
                df[minus_col] = adx_data.iloc[:, 2]
            else:
                df = CommonIndicators._dmi_manual(df, period, plus_col, minus_col)
        else:
            df = CommonIndicators._dmi_manual(df, period, plus_col, minus_col)
        return df

    @staticmethod
    def _dmi_manual(df: pd.DataFrame, period: int, plus_col: str, minus_col: str) -> pd.DataFrame:
        up_move = df["high"].diff()
        down_move = -df["low"].diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        atr_col = f"atr_{period}"
        if atr_col not in df.columns:
            CommonIndicators.add_atr(df, period=period)
        df[plus_col] = 100 * plus_dm.ewm(alpha=1/period, min_periods=period).mean() / df[atr_col]
        df[minus_col] = 100 * minus_dm.ewm(alpha=1/period, min_periods=period).mean() / df[atr_col]
        return df

    # ══════════════════════════════════════════════════════════
    # Pivot Points — Utilisé par : PivotPointReversal
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute les Pivot Points classiques (P, S1, S2, R1, R2).
        Calculés sur la bougie précédente (shift 1).
        Colonnes ajoutées : pivot, s1, s2, r1, r2
        """
        h = df["high"].shift(1)
        l = df["low"].shift(1)
        c = df["close"].shift(1)
        pivot = (h + l + c) / 3
        df["pivot"] = pivot
        df["s1"] = 2 * pivot - h
        df["r1"] = 2 * pivot - l
        df["s2"] = pivot - (h - l)
        df["r2"] = pivot + (h - l)
        return df

    # ══════════════════════════════════════════════════════════
    # Chandelier Exit — Utilisé par : ChandelierExit
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def add_chandelier_exit(
        df: pd.DataFrame,
        period: int = 22,
        atr_mult: float = 3.0,
    ) -> pd.DataFrame:
        """
        Ajoute le Chandelier Exit (Tushar Chande).
        Long : highest_high(period) - ATR(period) * mult
        Short : lowest_low(period) + ATR(period) * mult
        Colonnes ajoutées : chandelier_long_{period}, chandelier_short_{period}
        """
        atr_col = f"atr_{period}"
        if atr_col not in df.columns:
            CommonIndicators.add_atr(df, period=period)
        highest = df["high"].rolling(window=period).max()
        lowest = df["low"].rolling(window=period).min()
        df[f"chandelier_long_{period}"] = highest - atr_mult * df[atr_col]
        df[f"chandelier_short_{period}"] = lowest + atr_mult * df[atr_col]
        return df

    # ── Batch 3 Indicators ──────────────────────────────────────

    @staticmethod
    def add_kama(
        df: pd.DataFrame,
        period: int = 10,
        fast_sc: int = 2,
        slow_sc: int = 30,
    ) -> pd.DataFrame:
        """
        Kaufman Adaptive Moving Average (KAMA).
        S'accelere en tendance, ralentit en range via le ratio signal/bruit.
        Colonne ajoutee : kama_{period}
        """
        col = f"kama_{period}"
        if col in df.columns:
            return df

        close = df["close"].values.copy()
        kama = np.full(len(close), np.nan)

        fast_alpha = 2.0 / (fast_sc + 1)
        slow_alpha = 2.0 / (slow_sc + 1)

        if len(close) <= period:
            df[col] = kama
            return df

        kama[period - 1] = close[period - 1]

        for i in range(period, len(close)):
            signal = abs(close[i] - close[i - period])
            noise = sum(abs(close[j] - close[j - 1]) for j in range(i - period + 1, i + 1))
            if noise == 0:
                er = 0.0
            else:
                er = signal / noise
            sc = (er * (fast_alpha - slow_alpha) + slow_alpha) ** 2
            kama[i] = kama[i - 1] + sc * (close[i] - kama[i - 1])

        df[col] = kama
        return df

    @staticmethod
    def add_cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Commodity Channel Index — deviation normalisee du prix.
        CCI = (TP - SMA(TP)) / (0.015 * MeanDeviation)
        Colonne ajoutee : cci_{period}
        """
        col = f"cci_{period}"
        if col in df.columns:
            return df

        try:
            if pta is not None:
                result = pta.cci(df["high"], df["low"], df["close"], length=period)
                if result is not None and not result.isna().all():
                    df[col] = result
                    return df
        except Exception:
            pass

        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(window=period).mean()
        mean_dev = tp.rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        df[col] = (tp - sma_tp) / (0.015 * mean_dev)
        return df

    @staticmethod
    def add_obv(df: pd.DataFrame, sma_period: int = 20) -> pd.DataFrame:
        """
        On-Balance Volume + SMA.
        Colonnes ajoutees : obv, obv_sma_{sma_period}
        """
        sma_col = f"obv_sma_{sma_period}"
        if "obv" in df.columns and sma_col in df.columns:
            return df

        if "obv" not in df.columns:
            try:
                if pta is not None:
                    result = pta.obv(df["close"], df["volume"])
                    if result is not None and not result.isna().all():
                        df["obv"] = result
                    else:
                        raise ValueError
                else:
                    raise ValueError
            except Exception:
                direction = np.where(
                    df["close"] > df["close"].shift(1), 1,
                    np.where(df["close"] < df["close"].shift(1), -1, 0)
                )
                df["obv"] = (df["volume"] * direction).cumsum()

        if sma_col not in df.columns:
            df[sma_col] = df["obv"].rolling(window=sma_period).mean()

        return df

    @staticmethod
    def add_vwap_bands(
        df: pd.DataFrame,
        period: int = 20,
        std_mult: float = 2.0,
    ) -> pd.DataFrame:
        """
        VWAP rolling + bandes ecart-type.
        Colonnes ajoutees : vwap_{period}, vwap_upper_{period}, vwap_lower_{period}
        """
        vwap_col = f"vwap_{period}"
        if vwap_col in df.columns:
            return df

        tp = (df["high"] + df["low"] + df["close"]) / 3
        tp_vol = tp * df["volume"]

        cum_tp_vol = tp_vol.rolling(window=period).sum()
        cum_vol = df["volume"].rolling(window=period).sum()

        df[vwap_col] = cum_tp_vol / cum_vol

        # Ecart-type du prix par rapport au VWAP
        diff_sq = ((tp - df[vwap_col]) ** 2)
        vwap_std = diff_sq.rolling(window=period).mean().apply(np.sqrt)
        df[f"vwap_upper_{period}"] = df[vwap_col] + std_mult * vwap_std
        df[f"vwap_lower_{period}"] = df[vwap_col] - std_mult * vwap_std

        return df
