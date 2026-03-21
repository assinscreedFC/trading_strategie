# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : CombinedBinHAndClucV8
# CATEGORIE : Mean-Reversion — Bollinger Bands custom (scalping)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Combine 2 approches BB mean-reversion :
# - BinH : close < BB lower custom + confirmations (bbdelta, tail)
# - Cluc : close < BB lower + closedelta + volume
# TF : 5min pour du scalping rapide
# SOURCE : p-zombie/freqtrade, berlinguyinca — classique Freqtrade
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


class CombinedBinHAndClucV8(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "5m"
    startup_candle_count = 50

    minimal_roi = {"0": 0.05, "30": 0.025, "60": 0.015, "120": 0.005}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    bb_period = IntParameter(15, 30, default=20, space="buy")
    bb_std = IntParameter(15, 30, default=20, space="buy")  # /10 → 1.5 a 3.0
    bb_delta_factor = IntParameter(5, 20, default=10, space="buy")  # /1000
    closedelta_factor = IntParameter(5, 25, default=15, space="buy")  # /1000
    tail_factor = IntParameter(5, 30, default=20, space="buy")  # /100 of bbdelta

    # ── Sell params ──
    sell_bb_offset = IntParameter(95, 105, default=100, space="sell")  # /100

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
            self._logger = TradeLogger(strategy_name="CombinedBinHAndClucV8")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # BB pour toutes les combinaisons period/std
        for bb_p in range(self.bb_period.low, self.bb_period.high + 1):
            for bb_s_int in range(self.bb_std.low, self.bb_std.high + 1):
                bb_s = bb_s_int / 10
                dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=bb_p, std_dev=bb_s)

        # Helpers
        dataframe["closedelta"] = (dataframe["close"] - dataframe["close"].shift()).abs()
        dataframe["tail"] = (dataframe["close"] - dataframe["low"]).abs()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_p = self.bb_period.value
        bb_s = self.bb_std.value / 10
        bb_lower = f"bb_lower_{bb_p}"
        bb_middle = f"bb_middle_{bb_p}"

        bbdelta_thresh = self.bb_delta_factor.value / 1000
        closedelta_thresh = self.closedelta_factor.value / 1000
        tail_pct = self.tail_factor.value / 100

        # BinH style entry
        bbdelta = (dataframe[bb_middle] - dataframe[bb_lower]).abs()

        buy_binh = (
            (dataframe["close"] < dataframe[bb_lower])
            & (bbdelta > dataframe["close"] * bbdelta_thresh)
            & (dataframe["tail"] > bbdelta * tail_pct)
            & (dataframe["closedelta"] > dataframe["close"] * closedelta_thresh)
            & (dataframe["volume"] > 0)
        )

        # Cluc style entry
        buy_cluc = (
            (dataframe["close"] < dataframe[bb_lower])
            & (dataframe["close"] < dataframe["close"].shift(1))
            & (dataframe["close"].shift(1) < dataframe["close"].shift(2))
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[buy_binh | buy_cluc, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_p = self.bb_period.value
        bb_middle = f"bb_middle_{bb_p}"
        sell_offset = self.sell_bb_offset.value / 100

        conditions = (
            dataframe["close"] > dataframe[bb_middle] * sell_offset
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
