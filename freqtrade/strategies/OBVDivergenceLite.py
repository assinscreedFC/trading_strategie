# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : OBVDivergenceLite
# CATEGORIE : Volume — OBV Divergence (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de OBVDivergence :
# - 2 params : rsi_entry (buy) + rsi_exit (sell)
# - lookback=5, rsi_period=14 fixes
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


class OBVDivergenceLite(IStrategy):
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

    # ── Hyperopt params (1 buy + 1 sell) ──
    rsi_entry = IntParameter(30, 60, default=50, space="buy")
    rsi_exit = IntParameter(60, 85, default=70, space="sell")

    # ── Params fixes ──
    LOOKBACK = 5
    RSI_PERIOD = 14

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
            self._logger = TradeLogger(strategy_name="OBVDivergenceLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)

        obv_direction = np.where(
            dataframe["close"] > dataframe["close"].shift(1), 1,
            np.where(dataframe["close"] < dataframe["close"].shift(1), -1, 0)
        )
        dataframe["obv"] = (dataframe["volume"] * obv_direction).cumsum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.RSI_PERIOD}"
        lb = self.LOOKBACK

        conditions = (
            (dataframe["close"] < dataframe["close"].shift(lb))
            & (dataframe["obv"] > dataframe["obv"].shift(lb))
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.RSI_PERIOD}"
        lb = self.LOOKBACK

        conditions = (
            (
                (dataframe["close"] > dataframe["close"].shift(lb))
                & (dataframe["obv"] < dataframe["obv"].shift(lb))
            )
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
