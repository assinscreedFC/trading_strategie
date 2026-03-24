# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : SmartMoneyConcepts
# CATÉGORIE : Nouvelle — Smart Money / Price Action
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Break of Structure bullish (close > swing high récent)
# 2. Prix a retracé dans une zone Fair Value Gap (FVG)
# 3. RSI < seuil d'entrée (pas de surachat)
# 4. Sortie : BOS bearish (close < swing low récent) OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class SmartMoneyConcepts(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    swing_lookback = IntParameter(3, 10, default=5, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(40, 65, default=60, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_logger"] = None
        state["_notifier"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="SmartMoneyConcepts")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # Swing highs/lows pour TOUTES les valeurs de lookback
        for lookback in range(self.swing_lookback.low, self.swing_lookback.high + 1):
            sh_col = f"swing_high_{lookback}"
            sl_col = f"swing_low_{lookback}"
            dataframe[sh_col] = np.nan
            dataframe[sl_col] = np.nan

            for i in range(lookback, len(dataframe) - lookback):
                high_val = dataframe["high"].iloc[i]
                is_swing = True
                for j in range(1, lookback + 1):
                    if high_val <= dataframe["high"].iloc[i - j] or high_val <= dataframe["high"].iloc[i + j]:
                        is_swing = False
                        break
                if is_swing:
                    dataframe.iloc[i, dataframe.columns.get_loc(sh_col)] = high_val

                low_val = dataframe["low"].iloc[i]
                is_swing = True
                for j in range(1, lookback + 1):
                    if low_val >= dataframe["low"].iloc[i - j] or low_val >= dataframe["low"].iloc[i + j]:
                        is_swing = False
                        break
                if is_swing:
                    dataframe.iloc[i, dataframe.columns.get_loc(sl_col)] = low_val

            dataframe[f"recent_swing_high_{lookback}"] = dataframe[sh_col].ffill()
            dataframe[f"recent_swing_low_{lookback}"] = dataframe[sl_col].ffill()

        # Fair Value Gap bullish : low[i] > high[i-2] (gap entre bougie i et i-2)
        dataframe["fvg_bullish"] = (
            dataframe["low"] > dataframe["high"].shift(2)
        ).astype(int)

        # Zone FVG : on marque aussi quand le prix est dans la zone d'un FVG récent
        # FVG zone = entre high[i-2] et low[i] quand le gap existe
        dataframe["fvg_top"] = np.where(
            dataframe["fvg_bullish"] == 1,
            dataframe["low"],
            np.nan,
        )
        dataframe["fvg_bottom"] = np.where(
            dataframe["fvg_bullish"] == 1,
            dataframe["high"].shift(2),
            np.nan,
        )
        # Forward-fill les zones FVG pour les utiliser dans les bougies suivantes
        dataframe["fvg_top"] = dataframe["fvg_top"].ffill()
        dataframe["fvg_bottom"] = dataframe["fvg_bottom"].ffill()

        # Prix dans la zone FVG (pullback dans le gap)
        dataframe["in_fvg_zone"] = (
            (dataframe["low"] <= dataframe["fvg_top"])
            & (dataframe["high"] >= dataframe["fvg_bottom"])
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        sh_col = f"recent_swing_high_{self.swing_lookback.value}"

        # Break of Structure bullish : close dépasse le dernier swing high
        bos_bullish = (
            (dataframe["close"] > dataframe[sh_col])
            & (dataframe["close"].shift(1) <= dataframe[sh_col].shift(1))
        )

        conditions = (
            bos_bullish
            & (dataframe["in_fvg_zone"] == 1)
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        sl_col = f"recent_swing_low_{self.swing_lookback.value}"

        # Break of Structure bearish : close passe sous le dernier swing low
        bos_bearish = dataframe["close"] < dataframe[sl_col]

        conditions = (
            bos_bearish
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
