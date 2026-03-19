# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : FibonacciPullback
# CATEGORIE : Retracement / Fibonacci
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Retracement de Fibonacci — acheter quand le prix retrace aux
# niveaux cles 38.2% ou 61.8% d'un swing recent.
# Ces niveaux agissent comme support naturel dans une tendance
# haussiere et offrent des entrees a probabilite elevee.
#
# ENTREE :
# 1. Close proche du niveau fib 38.2% ou 61.8% (tolerance configurable)
# 2. Close > fib_level (rebond confirme, pas juste un touch)
# 3. RSI < seuil (pas en surachat)
#
# SORTIE :
# Close >= swing_high * 0.98 (retour au sommet) OU RSI > seuil
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


class FibonacciPullback(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.15, "720": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    swing_period = IntParameter(10, 40, default=20, space="buy")
    fib_tolerance = DecimalParameter(0.005, 0.02, default=0.01, decimals=3, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(40, 65, default=55, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="FibonacciPullback")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer swing high/low pour TOUTES les valeurs de swing_period
        for sp in range(self.swing_period.low, self.swing_period.high + 1):
            dataframe[f"swing_high_{sp}"] = dataframe["high"].rolling(window=sp).max()
            dataframe[f"swing_low_{sp}"] = dataframe["low"].rolling(window=sp).min()

            swing_range = dataframe[f"swing_high_{sp}"] - dataframe[f"swing_low_{sp}"]
            dataframe[f"fib_382_{sp}"] = dataframe[f"swing_low_{sp}"] + 0.382 * swing_range
            dataframe[f"fib_618_{sp}"] = dataframe[f"swing_low_{sp}"] + 0.618 * swing_range

        # Pre-calculer RSI pour TOUTES les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sp = self.swing_period.value
        rsi_col = f"rsi_{self.rsi_period.value}"
        fib_382 = dataframe[f"fib_382_{sp}"]
        fib_618 = dataframe[f"fib_618_{sp}"]
        tol = self.fib_tolerance.value

        # Proche du niveau fib 38.2%
        near_382 = (
            (np.abs(dataframe["close"] - fib_382) / fib_382 < tol)
            & (dataframe["close"] > fib_382)
        )
        # Proche du niveau fib 61.8%
        near_618 = (
            (np.abs(dataframe["close"] - fib_618) / fib_618 < tol)
            & (dataframe["close"] > fib_618)
        )

        conditions = (
            (near_382 | near_618)
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sp = self.swing_period.value
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            # Prix revient au swing high
            (dataframe["close"] >= dataframe[f"swing_high_{sp}"] * 0.98)
            # OU RSI en surachat
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
