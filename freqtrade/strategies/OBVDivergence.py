# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : OBVDivergence
# CATÉGORIE : Volume — On-Balance Volume Divergence
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# OBV mesure la pression acheteuse/vendeuse via le volume cumulé.
# Une divergence haussière (prix baisse mais OBV monte) signale
# un retournement potentiel.
# 1. Prix lower low + OBV higher low → divergence haussière + RSI < 50
# 2. Sortie : prix higher high + OBV lower high → divergence baissière OU RSI > 70
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class OBVDivergence(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.03, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    lookback = IntParameter(3, 15, default=5, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(30, 60, default=50, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 85, default=70, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="OBVDivergence")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calc RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calc volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # OBV calc: cumulative sum of signed volume
        obv_direction = np.where(
            dataframe["close"] > dataframe["close"].shift(1), 1,
            np.where(dataframe["close"] < dataframe["close"].shift(1), -1, 0)
        )
        dataframe["obv"] = (dataframe["volume"] * obv_direction).cumsum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        lb = self.lookback.value

        # Bullish divergence: price lower low + OBV higher low + RSI < threshold
        conditions = (
            (dataframe["close"] < dataframe["close"].shift(lb))
            & (dataframe["obv"] > dataframe["obv"].shift(lb))
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        lb = self.lookback.value

        # Bearish divergence: price higher high + OBV lower high OR RSI > threshold
        conditions = (
            (
                (dataframe["close"] > dataframe["close"].shift(lb))
                & (dataframe["obv"] < dataframe["obv"].shift(lb))
            )
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
