# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : DMICrossover
# CATEGORIE : Trend — +DI/-DI Crossover with ADX Filter
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. +DI croise au-dessus de -DI (momentum haussier)
# 2. ADX > threshold (tendance forte)
# 3. Bougie verte + volume > 0
# 4. Sortie : +DI croise sous -DI OU ADX < threshold
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class DMICrossover(IStrategy):
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
    dmi_period = IntParameter(10, 20, default=14, space="buy")
    adx_threshold = IntParameter(20, 35, default=25, space="buy")

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
            self._logger = TradeLogger(strategy_name="DMICrossover")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # DMI (+DI, -DI) et ADX pour toutes les valeurs de dmi_period
        for p in range(self.dmi_period.low, self.dmi_period.high + 1):
            dataframe = CommonIndicators.add_dmi(dataframe, period=p)
            dataframe = CommonIndicators.add_adx(dataframe, period=p)

        # Volume SMA
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        plus_di = f"plus_di_{self.dmi_period.value}"
        minus_di = f"minus_di_{self.dmi_period.value}"
        adx_col = f"adx_{self.dmi_period.value}"

        conditions = (
            (dataframe[plus_di] > dataframe[minus_di])
            & (dataframe[plus_di].shift(1) <= dataframe[minus_di].shift(1))
            & (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        plus_di = f"plus_di_{self.dmi_period.value}"
        minus_di = f"minus_di_{self.dmi_period.value}"
        adx_col = f"adx_{self.dmi_period.value}"

        conditions = (
            (dataframe[plus_di] < dataframe[minus_di])
            & (dataframe[plus_di].shift(1) >= dataframe[minus_di].shift(1))
            | (dataframe[adx_col] < self.adx_threshold.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
