# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : CCIMomentumTrend
# CATEGORIE : Momentum — CCI Deviation Statistique
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# CCI mesure la deviation du prix par rapport a sa moyenne.
# 1. CCI crossover +100 (momentum fort)
# 2. CCI > +100 pendant 2 bougies (filtre persistence)
# 3. EMA trend filter + volume
# 4. Sortie : CCI < 0 (zero-crossing)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class CCIMomentumTrend(IStrategy):
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

    # ── Buy params ──
    cci_period = IntParameter(10, 30, default=20, space="buy")
    cci_entry = IntParameter(80, 150, default=100, space="buy")
    ema_period = IntParameter(30, 70, default=50, space="buy")
    persistence = IntParameter(1, 4, default=2, space="buy")

    # ── Sell params ──
    cci_exit = IntParameter(-20, 20, default=0, space="sell")

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
            self._logger = TradeLogger(strategy_name="CCIMomentumTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.cci_period.low, self.cci_period.high + 1):
            dataframe = CommonIndicators.add_cci(dataframe, period=p)

        for p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cci_col = f"cci_{self.cci_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        persist = self.persistence.value
        threshold = self.cci_entry.value

        # CCI > threshold pendant 'persist' bougies consecutives
        cci_above = dataframe[cci_col] > threshold
        for i in range(1, persist):
            cci_above = cci_above & (dataframe[cci_col].shift(i) > threshold)

        conditions = (
            cci_above
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cci_col = f"cci_{self.cci_period.value}"

        conditions = (
            dataframe[cci_col] < self.cci_exit.value
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
