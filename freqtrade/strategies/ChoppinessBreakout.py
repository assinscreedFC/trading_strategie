# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ChoppinessBreakout
# CATEGORIE : Breakout — Choppiness Index Trend Filter
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Choppiness < threshold (marche en tendance, pas choppy)
# 2. Close > breakout_high (cassure haussiere)
# 3. Volume > volume_sma (confirmation volume)
# 4. Close > EMA filter (tendance globale)
# 5. Sortie : choppiness > exit_threshold OU close < breakout_low
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ChoppinessBreakout(IStrategy):
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
    chop_period = IntParameter(10, 20, default=14, space="buy")
    chop_threshold = IntParameter(30, 45, default=38, space="buy")
    breakout_period = IntParameter(15, 30, default=20, space="buy")
    ema_filter = IntParameter(30, 60, default=50, space="buy")

    # ── Sell params ──
    chop_exit = IntParameter(55, 70, default=62, space="sell")

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
            self._logger = TradeLogger(strategy_name="ChoppinessBreakout")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Choppiness Index pour toutes les valeurs de chop_period
        for p in range(self.chop_period.low, self.chop_period.high + 1):
            dataframe = CommonIndicators.add_choppiness(dataframe, period=p)

        # Breakout levels pour toutes les valeurs de breakout_period
        for p in range(self.breakout_period.low, self.breakout_period.high + 1):
            dataframe = CommonIndicators.add_breakout_levels(dataframe, period=p)

        # EMA filter pour toutes les valeurs
        for p in range(self.ema_filter.low, self.ema_filter.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        # Volume SMA
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"choppiness_{self.chop_period.value}"
        bo_high = f"breakout_high_{self.breakout_period.value}"
        ema_col = f"ema_{self.ema_filter.value}"

        conditions = (
            (dataframe[chop_col] < self.chop_threshold.value)
            & (dataframe["close"] > dataframe[bo_high].shift(1))
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"choppiness_{self.chop_period.value}"
        bo_low = f"breakout_low_{self.breakout_period.value}"

        conditions = (
            (dataframe[chop_col] > self.chop_exit.value)
            | (dataframe["close"] < dataframe[bo_low].shift(1))
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
