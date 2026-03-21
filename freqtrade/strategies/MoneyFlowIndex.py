# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : MoneyFlowIndex
# CATEGORIE : Volume — MFI Oversold/Overbought
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MoneyFlowIndex(IStrategy):
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
    mfi_period = IntParameter(10, 20, default=14, space="buy")
    mfi_entry = IntParameter(15, 30, default=20, space="buy")
    ema_filter = IntParameter(30, 60, default=50, space="buy")

    # ── Sell params ──
    mfi_exit = IntParameter(70, 85, default=80, space="sell")

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
            self._logger = TradeLogger(strategy_name="MoneyFlowIndex")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for mfi_p in range(self.mfi_period.low, self.mfi_period.high + 1):
            dataframe = CommonIndicators.add_mfi(dataframe, period=mfi_p)

        for ema_p in range(self.ema_filter.low, self.ema_filter.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mfi_col = f"mfi_{self.mfi_period.value}"
        ema_col = f"ema_{self.ema_filter.value}"

        conditions = (
            (dataframe[mfi_col] < self.mfi_entry.value)
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mfi_col = f"mfi_{self.mfi_period.value}"

        conditions = (
            dataframe[mfi_col] > self.mfi_exit.value
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
