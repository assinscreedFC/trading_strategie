# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : CumulativeRSI
# CATEGORIE : Mean-Reversion — Cumulative RSI(2) de Larry Connors
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Somme du RSI(2) sur N jours. Quand la somme est tres basse,
# le marche est en survente cumulee → rebond probable.
# 1. Cumulative RSI(2) sur cum_days < cum_threshold + prix > SMA(200) → long
# 2. Sortie : Close > SMA(5) (rebond court terme)
# SOURCE : QuantifiedStrategies — 280k events, WR 65%, SPY WR 83%
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class CumulativeRSI(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 210

    minimal_roi = {"0": 0.08, "120": 0.04, "360": 0.02, "720": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    rsi_period = IntParameter(2, 5, default=2, space="buy")
    cum_days = IntParameter(2, 5, default=2, space="buy")
    cum_threshold = IntParameter(5, 20, default=10, space="buy")
    sma_trend = IntParameter(150, 250, default=200, space="buy")

    # ── Sell params ──
    sma_exit = IntParameter(3, 10, default=5, space="sell")

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
            self._logger = TradeLogger(strategy_name="CumulativeRSI")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        for sma_p in range(self.sma_trend.low, self.sma_trend.high + 1):
            dataframe = CommonIndicators.add_sma(dataframe, period=sma_p)

        for sma_e in range(self.sma_exit.low, self.sma_exit.high + 1):
            dataframe = CommonIndicators.add_sma(dataframe, period=sma_e)

        # Pre-calc cumulative RSI pour toutes combinaisons
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            rsi_col = f"rsi_{rsi_p}"
            for cum_d in range(self.cum_days.low, self.cum_days.high + 1):
                dataframe[f"cum_rsi_{rsi_p}_{cum_d}"] = dataframe[rsi_col].rolling(window=cum_d).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cum_col = f"cum_rsi_{self.rsi_period.value}_{self.cum_days.value}"
        sma_col = f"sma_{self.sma_trend.value}"

        conditions = (
            (dataframe[cum_col] < self.cum_threshold.value)
            & (dataframe["close"] > dataframe[sma_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sma_exit_col = f"sma_{self.sma_exit.value}"

        conditions = (
            dataframe["close"] > dataframe[sma_exit_col]
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
