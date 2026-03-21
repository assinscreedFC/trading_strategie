# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : RSI2Connors
# CATEGORIE : Mean-Reversion — RSI(2) de Larry Connors adapte crypto
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# RSI(2) ultra-court terme detecte les conditions de survente extreme.
# Filtre tendance SMA(200) pour n'acheter que dans un uptrend.
# 1. RSI(2) < seuil_entree (ex: 5) + prix > SMA(200) → long
# 2. Sortie : RSI(2) > seuil_sortie (ex: 70)
# SOURCE : QuantifiedStrategies — WR 70-80% sur actions depuis 1990
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class RSI2Connors(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 210

    minimal_roi = {"0": 0.08, "120": 0.04, "360": 0.02, "720": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    rsi_period = IntParameter(2, 5, default=2, space="buy")
    rsi_entry = IntParameter(3, 15, default=5, space="buy")
    sma_period = IntParameter(150, 250, default=200, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(50, 90, default=70, space="sell")

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
            self._logger = TradeLogger(strategy_name="RSI2Connors")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calc RSI pour TOUTES les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calc SMA pour TOUTES les valeurs possibles
        for sma_p in range(self.sma_period.low, self.sma_period.high + 1):
            dataframe = CommonIndicators.add_sma(dataframe, period=sma_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        sma_col = f"sma_{self.sma_period.value}"

        conditions = (
            (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["close"] > dataframe[sma_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            dataframe[rsi_col] > self.rsi_exit.value
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
