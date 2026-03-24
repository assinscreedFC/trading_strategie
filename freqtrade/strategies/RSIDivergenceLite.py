# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : RSIDivergenceLite
# CATEGORIE : Mean Reversion — RSI Bullish Divergence (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de RSIDivergence :
# - 2 params hyperopt seulement : rsi_period, rsi_exit
# - swing_lookback=10 et ema_filter=50 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class RSIDivergenceLite(IStrategy):
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
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_exit = IntParameter(65, 80, default=70, space="sell")

    # ── Params fixes ──
    SWING_LOOKBACK = 10
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
            self._logger = TradeLogger(strategy_name="RSIDivergenceLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_FILTER)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        ema_col = f"ema_{self.EMA_FILTER}"
        lb = self.SWING_LOOKBACK

        conditions = (
            (dataframe["low"] < dataframe["low"].shift(lb))
            & (dataframe[rsi_col] > dataframe[rsi_col].shift(lb))
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = dataframe[rsi_col] > self.rsi_exit.value

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
