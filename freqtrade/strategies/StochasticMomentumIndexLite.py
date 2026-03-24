# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : StochasticMomentumIndexLite
# CATEGORIE : Mean Reversion — Stochastic Crossover in Oversold (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de StochasticMomentumIndex :
# - 2 params hyperopt seulement : k_period, stoch_overbought
# - stoch_oversold=20, ema_filter=50, d_period=3 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class StochasticMomentumIndexLite(IStrategy):
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
    k_period = IntParameter(10, 21, default=14, space="buy")
    stoch_overbought = IntParameter(70, 90, default=80, space="sell")

    # ── Params fixes ──
    STOCH_OVERSOLD = 20
    EMA_FILTER = 50
    D_PERIOD = 3

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
            self._logger = TradeLogger(strategy_name="StochasticMomentumIndexLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.k_period.low, self.k_period.high + 1):
            dataframe = CommonIndicators.add_stochastic(dataframe, k_period=p, d_period=self.D_PERIOD)

        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_FILTER)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        k_col = f"stoch_k_{self.k_period.value}"
        d_col = f"stoch_d_{self.k_period.value}"
        ema_col = f"ema_{self.EMA_FILTER}"

        conditions = (
            (dataframe[k_col] > dataframe[d_col])
            & (dataframe[k_col].shift(1) <= dataframe[d_col].shift(1))
            & (dataframe[k_col] < self.STOCH_OVERSOLD)
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        k_col = f"stoch_k_{self.k_period.value}"
        d_col = f"stoch_d_{self.k_period.value}"

        conditions = (
            (dataframe[k_col] < dataframe[d_col])
            & (dataframe[k_col].shift(1) >= dataframe[d_col].shift(1))
            & (dataframe[k_col] > self.stoch_overbought.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
