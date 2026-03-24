# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : MACDDivergenceLite
# CATEGORIE : Divergence — MACD (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de MACDDivergence :
# - 2 params : rsi_entry (buy) + rsi_exit (sell)
# - lookback=5, rsi_period=14, volume_period=20, volume_mult=0.8 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MACDDivergenceLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.12, "480": 0.06, "1440": 0.03}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    rsi_entry = IntParameter(30, 55, default=45, space="buy")
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

    # ── Params fixes ──
    LOOKBACK = 5
    RSI_PERIOD = 14
    VOLUME_PERIOD = 20
    VOLUME_MULT = 0.8

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
            self._logger = TradeLogger(strategy_name="MACDDivergenceLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.VOLUME_PERIOD)
        dataframe = CommonIndicators.add_macd(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.RSI_PERIOD}"
        vol_sma_col = f"volume_sma_{self.VOLUME_PERIOD}"
        lb = self.LOOKBACK

        price_lower_low = dataframe["close"] < dataframe["close"].shift(lb)
        macd_higher_low = dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(lb)

        conditions = (
            price_lower_low
            & macd_higher_low
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > dataframe[vol_sma_col] * self.VOLUME_MULT)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        macd_declining_3 = (
            (dataframe["macd_histogram"] < 0)
            & (dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1))
            & (dataframe["macd_histogram"].shift(1) < dataframe["macd_histogram"].shift(2))
        )

        conditions = macd_declining_3 | (dataframe[rsi_col] > self.rsi_exit.value)

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
