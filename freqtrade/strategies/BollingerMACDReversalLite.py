# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : BollingerMACDReversalLite
# CATEGORIE : Mean-reversion — BB + MACD Confirmation (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de BollingerMACDReversal :
# - 2 params hyperopt seulement : bb_period, rsi_exit
# - rsi_period=14 et rsi_entry=40 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class BollingerMACDReversalLite(IStrategy):
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
    bb_period = IntParameter(15, 30, default=20, space="buy")
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

    # ── Params fixes ──
    RSI_PERIOD = 14
    RSI_ENTRY = 40

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
            self._logger = TradeLogger(strategy_name="BollingerMACDReversalLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.bb_period.low, self.bb_period.high + 1):
            dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=p)

        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)
        dataframe = CommonIndicators.add_macd(dataframe)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_lower_col = f"bb_lower_{self.bb_period.value}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        macd_rising = (
            dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1)
        )

        conditions = (
            (dataframe["close"] <= dataframe[bb_lower_col] * 1.01)
            & macd_rising
            & (dataframe[rsi_col] < self.RSI_ENTRY)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_middle_col = f"bb_middle_{self.bb_period.value}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        conditions = (
            (dataframe["close"] >= dataframe[bb_middle_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
