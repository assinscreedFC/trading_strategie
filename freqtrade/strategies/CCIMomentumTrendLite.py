# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : CCIMomentumTrendLite
# CATEGORIE : Momentum — CCI Deviation (Simplifie)
# ══════════════════════════════════════════════════════════════
# Version simplifiee de CCIMomentumTrend :
# - 2 params : cci_period (buy) + cci_exit (sell)
# - cci_entry=100, ema=50, persistence=2 fixes
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class CCIMomentumTrendLite(IStrategy):
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

    # ── Hyperopt params (1 buy + 1 sell) ──
    cci_period = IntParameter(14, 30, default=20, space="buy")
    cci_exit = IntParameter(-20, 20, default=0, space="sell")

    # ── Params fixes ──
    CCI_ENTRY = 100
    EMA_PERIOD = 50
    PERSISTENCE = 2

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
            self._logger = TradeLogger(strategy_name="CCIMomentumTrendLite")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.cci_period.low, self.cci_period.high + 1):
            dataframe = CommonIndicators.add_cci(dataframe, period=p)

        dataframe = CommonIndicators.add_ema(dataframe, period=self.EMA_PERIOD)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cci_col = f"cci_{self.cci_period.value}"
        ema_col = f"ema_{self.EMA_PERIOD}"

        # CCI > CCI_ENTRY pendant PERSISTENCE bougies consecutives
        cci_above = dataframe[cci_col] > self.CCI_ENTRY
        for i in range(1, self.PERSISTENCE):
            cci_above = cci_above & (dataframe[cci_col].shift(i) > self.CCI_ENTRY)

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

        conditions = dataframe[cci_col] < self.cci_exit.value

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
