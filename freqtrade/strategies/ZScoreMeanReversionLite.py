# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ZScoreMeanReversionLite
# CATEGORIE : Mean Reversion — Z-Score Extreme Low (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de ZScoreMeanReversion :
# - 2 params hyperopt seulement : zscore_period, zscore_exit
# - bb_period=20 et zscore_entry=-2.0 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ZScoreMeanReversionLite(IStrategy):
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
    zscore_period = IntParameter(15, 40, default=20, space="buy")
    zscore_exit = IntParameter(0, 20, default=5, space="sell")  # /10

    # ── Params fixes ──
    BB_PERIOD = 20
    ZSCORE_ENTRY = -2.0

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
            self._logger = TradeLogger(strategy_name="ZScoreMeanReversionLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for zp in range(self.zscore_period.low, self.zscore_period.high + 1):
            sma = dataframe["close"].rolling(window=zp).mean()
            std = dataframe["close"].rolling(window=zp).std()
            dataframe[f"zscore_{zp}"] = (dataframe["close"] - sma) / std

        dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=self.BB_PERIOD)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        zscore_col = f"zscore_{self.zscore_period.value}"
        bb_lower_col = f"bb_lower_{self.BB_PERIOD}"

        conditions = (
            (dataframe[zscore_col] < self.ZSCORE_ENTRY)
            & (dataframe["close"] < dataframe[bb_lower_col])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        zscore_col = f"zscore_{self.zscore_period.value}"
        threshold = self.zscore_exit.value / 10.0

        conditions = dataframe[zscore_col] > threshold

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
