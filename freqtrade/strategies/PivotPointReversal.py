# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : PivotPointReversal
# CATEGORIE : Reversal — Bounce off Pivot Support S1
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Close pres de S1 (entre s1*0.99 et s1*1.01)
# 2. RSI < rsi_entry (zone de faiblesse)
# 3. Bougie verte + volume > 0
# 4. Sortie : close >= R1 OU RSI > rsi_exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class PivotPointReversal(IStrategy):
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
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_entry = IntParameter(25, 45, default=35, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 80, default=75, space="sell")

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
            self._logger = TradeLogger(strategy_name="PivotPointReversal")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pivot Points
        dataframe = CommonIndicators.add_pivot_points(dataframe)

        # RSI pour toutes les valeurs de rsi_period
        for p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=p)

        # Volume SMA
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] > dataframe["s1"] * 0.99)
            & (dataframe["close"] < dataframe["s1"] * 1.01)
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] >= dataframe["r1"])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
