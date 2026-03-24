# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : MARibbonStack
# CATÉGORIE : Nouvelle — Trend Following avec MA Ribbon
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Toutes les EMAs empilées dans l'ordre (EMA1 > EMA2 > EMA3 > EMA4 > EMA5)
# 2. Close > EMA la plus rapide
# 3. Volume > multiplicateur * moyenne
# 4. Sortie : ribbon collapse (EMA1 < EMA2 OU EMA2 < EMA3) OU close < EMA5
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MARibbonStack(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.12, "480": 0.06, "1440": 0.03}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_1 = IntParameter(5, 15, default=10, space="buy")
    ema_2 = IntParameter(15, 25, default=20, space="buy")
    ema_3 = IntParameter(25, 35, default=30, space="buy")
    ema_4 = IntParameter(35, 45, default=40, space="buy")
    ema_5 = IntParameter(45, 60, default=50, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

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
            self._logger = TradeLogger(strategy_name="MARibbonStack")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calc EMA pour TOUTES les valeurs possibles de chaque param (hyperopt-safe)
        all_ema_values: set[int] = set()
        for param in (self.ema_1, self.ema_2, self.ema_3, self.ema_4, self.ema_5):
            all_ema_values.update(range(param.low, param.high + 1))
        for ema_p in sorted(all_ema_values):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calc volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        e1 = f"ema_{self.ema_1.value}"
        e2 = f"ema_{self.ema_2.value}"
        e3 = f"ema_{self.ema_3.value}"
        e4 = f"ema_{self.ema_4.value}"
        e5 = f"ema_{self.ema_5.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe[e1] > dataframe[e2])
            & (dataframe[e2] > dataframe[e3])
            & (dataframe[e3] > dataframe[e4])
            & (dataframe[e4] > dataframe[e5])
            & (dataframe["close"] > dataframe[e1])
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        e1 = f"ema_{self.ema_1.value}"
        e2 = f"ema_{self.ema_2.value}"
        e3 = f"ema_{self.ema_3.value}"
        e5 = f"ema_{self.ema_5.value}"

        conditions = (
            (dataframe[e1] < dataframe[e2])
            | (dataframe[e2] < dataframe[e3])
            | (dataframe["close"] < dataframe[e5])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
