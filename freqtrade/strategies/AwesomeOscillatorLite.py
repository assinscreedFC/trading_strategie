# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : AwesomeOscillatorLite
# CATEGORIE : Momentum — Awesome Oscillator (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de AwesomeOscillator :
# - 2 params : ao_fast (buy) + rsi_exit (sell)
# - ao_slow=34, rsi_period=14 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class AwesomeOscillatorLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.10, "120": 0.05, "360": 0.03, "720": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    ao_fast = IntParameter(3, 8, default=5, space="buy")
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    # ── Params fixes ──
    AO_SLOW = 34
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
            self._logger = TradeLogger(strategy_name="AwesomeOscillatorLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        dataframe["median_price"] = (dataframe["high"] + dataframe["low"]) / 2

        sma_slow = dataframe["median_price"].rolling(window=self.AO_SLOW).mean()
        for fast in range(self.ao_fast.low, self.ao_fast.high + 1):
            sma_fast = dataframe["median_price"].rolling(window=fast).mean()
            dataframe[f"ao_{fast}"] = sma_fast - sma_slow

        dataframe = CommonIndicators.add_rsi(dataframe, period=self.RSI_PERIOD)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ao_col = f"ao_{self.ao_fast.value}"

        # Zero-line cross (AO passe de negatif a positif)
        zero_cross = (
            (dataframe[ao_col] > 0)
            & (dataframe[ao_col].shift(1) <= 0)
        )

        # Twin Peaks sous zero (2e creux plus haut + bar vert)
        twin_peaks = (
            (dataframe[ao_col] < 0)
            & (dataframe[ao_col] > dataframe[ao_col].shift(1))
            & (dataframe[ao_col].shift(1) < dataframe[ao_col].shift(2))
        )

        dataframe.loc[(zero_cross | twin_peaks) & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ao_col = f"ao_{self.ao_fast.value}"
        rsi_col = f"rsi_{self.RSI_PERIOD}"

        conditions = (
            (
                (dataframe[ao_col] < 0)
                & (dataframe[ao_col].shift(1) >= 0)
            )
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
