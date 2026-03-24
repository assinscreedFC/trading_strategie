# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ChoppinessBreakoutLite
# CATEGORIE : Breakout — Choppiness Index Trend Filter (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de ChoppinessBreakout :
# - 2 params hyperopt seulement : chop_period, chop_exit
# - chop_threshold=38, breakout_period=20, ema_filter=50 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ChoppinessBreakoutLite(IStrategy):
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

    # ── Hyperopt params (2 seulement) ──
    chop_period = IntParameter(10, 20, default=14, space="buy")
    chop_exit = IntParameter(55, 70, default=62, space="sell")

    # ── Params fixes ──
    CHOP_THRESHOLD = 38
    BREAKOUT_PERIOD = 20
    EMA_FILTER = 50

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
            self._logger = TradeLogger(strategy_name="ChoppinessBreakoutLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.chop_period.low, self.chop_period.high + 1):
            dataframe = CommonIndicators.add_choppiness(dataframe, period=p)

        dataframe = CommonIndicators.add_breakout_levels(dataframe, period=self.BREAKOUT_PERIOD)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_FILTER)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"choppiness_{self.chop_period.value}"
        bo_high = f"breakout_high_{self.BREAKOUT_PERIOD}"
        ema_col = f"ema_{self.EMA_FILTER}"

        conditions = (
            (dataframe[chop_col] < self.CHOP_THRESHOLD)
            & (dataframe["close"] > dataframe[bo_high].shift(1))
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"choppiness_{self.chop_period.value}"
        bo_low = f"breakout_low_{self.BREAKOUT_PERIOD}"

        conditions = (
            (dataframe[chop_col] > self.chop_exit.value)
            | (dataframe["close"] < dataframe[bo_low].shift(1))
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
