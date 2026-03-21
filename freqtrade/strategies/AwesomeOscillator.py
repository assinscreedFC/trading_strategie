# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : AwesomeOscillator
# CATEGORIE : Momentum — Awesome Oscillator (Bill Williams)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# AO = SMA(5, median price) - SMA(34, median price)
# Signaux d'entree :
# 1. Twin Peaks : 2 creux sous zero, le 2e plus haut + bar vert → long
# 2. Zero-Line Cross : AO passe de negatif a positif → long
# Sortie : AO repasse sous zero ou divergence baissiere
# SOURCE : Bill Williams — Trading Chaos
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


class AwesomeOscillator(IStrategy):
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

    # ── Buy params ──
    ao_fast = IntParameter(3, 8, default=5, space="buy")
    ao_slow = IntParameter(25, 45, default=34, space="buy")
    twin_peak_lookback = IntParameter(5, 20, default=10, space="buy")

    # ── Sell params ──
    # Sortie sur AO < 0 ou trailing stop

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
            self._logger = TradeLogger(strategy_name="AwesomeOscillator")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Median price
        dataframe["median_price"] = (dataframe["high"] + dataframe["low"]) / 2

        # AO pour toutes les combinaisons fast/slow
        for fast in range(self.ao_fast.low, self.ao_fast.high + 1):
            for slow in range(self.ao_slow.low, self.ao_slow.high + 1):
                sma_fast = dataframe["median_price"].rolling(window=fast).mean()
                sma_slow = dataframe["median_price"].rolling(window=slow).mean()
                dataframe[f"ao_{fast}_{slow}"] = sma_fast - sma_slow

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ao_col = f"ao_{self.ao_fast.value}_{self.ao_slow.value}"
        lb = self.twin_peak_lookback.value

        # Signal 1 : Zero-line cross (AO passe de negatif a positif)
        zero_cross = (
            (dataframe[ao_col] > 0)
            & (dataframe[ao_col].shift(1) <= 0)
        )

        # Signal 2 : Twin Peaks sous zero
        # 2e creux > 1er creux + bar vert (AO montant)
        ao_min_prev = dataframe[ao_col].rolling(window=lb).min().shift(1)
        twin_peaks = (
            (dataframe[ao_col] < 0)
            & (dataframe[ao_col] > dataframe[ao_col].shift(1))  # Bar vert
            & (dataframe[ao_col].shift(1) < dataframe[ao_col].shift(2))  # Etait un creux
            & (dataframe[ao_col].shift(1) > ao_min_prev)  # 2e creux plus haut
        )

        dataframe.loc[(zero_cross | twin_peaks) & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ao_col = f"ao_{self.ao_fast.value}_{self.ao_slow.value}"

        # Sortie : AO repasse sous zero
        conditions = (
            (dataframe[ao_col] < 0)
            & (dataframe[ao_col].shift(1) >= 0)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
