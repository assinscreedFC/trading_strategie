# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : VolumeProfileAccumulation
# CATEGORIE : Volume-at-price — VWAP Rolling + Bandes
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Les zones VWAP sont des "value areas" ou le prix revient.
# 1. Close < VWAP lower band (prix sous la valeur)
# 2. RSI < 50 (pas en surachat)
# 3. Volume > SMA (confirmation d'interet)
# 4. Sortie : close > VWAP + 2 ATR OU RSI > 70
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class VolumeProfileAccumulation(IStrategy):
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
    vwap_period = IntParameter(10, 30, default=20, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(35, 55, default=50, space="buy")
    atr_period = IntParameter(10, 20, default=14, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 80, default=70, space="sell")
    atr_exit_mult = IntParameter(15, 30, default=20, space="sell")  # /10 → 1.5-3.0

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
            self._logger = TradeLogger(strategy_name="VolumeProfileAccumulation")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.vwap_period.low, self.vwap_period.high + 1):
            dataframe = CommonIndicators.add_vwap_bands(dataframe, period=p)

        for p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=p)

        for p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vwap_lower = f"vwap_lower_{self.vwap_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] < dataframe[vwap_lower])
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vwap_col = f"vwap_{self.vwap_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        atr_col = f"atr_{self.atr_period.value}"
        atr_mult = self.atr_exit_mult.value / 10.0

        conditions = (
            (dataframe["close"] > dataframe[vwap_col] + atr_mult * dataframe[atr_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
