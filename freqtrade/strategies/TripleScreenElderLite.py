# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : TripleScreenElderLite
# CATEGORIE : Multi-TF — Elder Triple Screen (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de TripleScreenElder :
# - 2 params : rsi_period (buy) + rsi_exit (sell)
# - rsi_entry=40 fixe, MACD 12/26/9 fixe, daily TF
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
from typing import List, Tuple

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class TripleScreenElderLite(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 200

    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.03, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Hyperopt params (1 buy + 1 sell) ──
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    # ── Params fixes ──
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
            self._logger = TradeLogger(strategy_name="TripleScreenElderLite")
            self._notifier = TelegramNotifier()

    def informative_pairs(self) -> List[Tuple[str, str]]:
        return [(pair, "1d") for pair in self.dp.current_whitelist()]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Screen 1: 1d MACD
        informative_1d = self.dp.get_pair_dataframe(metadata["pair"], "1d")
        informative_1d = CommonIndicators.add_macd(informative_1d, fast=12, slow=26, signal=9)

        dataframe = merge_informative_pair(dataframe, informative_1d, "4h", "1d", ffill=True)

        # Screen 2: 4h RSI
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            # Screen 1: 1d MACD histogram rising
            (dataframe["macd_histogram_1d"] > dataframe["macd_histogram_1d"].shift(1))
            # Screen 2: 4h RSI pullback
            & (dataframe[rsi_col] < self.RSI_ENTRY)
            # Screen 3: green candle confirmation
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["macd_histogram_1d"] < dataframe["macd_histogram_1d"].shift(1))
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
