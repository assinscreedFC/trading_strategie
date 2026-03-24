# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : KAMAAdaptiveTrend
# CATEGORIE : Trend-following adaptatif (Kaufman)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# KAMA (Kaufman Adaptive MA) s'accelere en tendance, ralentit en range.
# 1. KAMA_fast > KAMA_slow (crossover haussier)
# 2. ADX > seuil (confirmation tendance)
# 3. Volume > SMA volume
# 4. Sortie : KAMA_fast < KAMA_slow
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class KAMAAdaptiveTrend(IStrategy):
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
    kama_fast_period = IntParameter(5, 15, default=10, space="buy")
    kama_slow_period = IntParameter(20, 40, default=30, space="buy")
    adx_period = IntParameter(10, 20, default=14, space="buy")
    adx_threshold = IntParameter(15, 30, default=20, space="buy")

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
            self._logger = TradeLogger(strategy_name="KAMAAdaptiveTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.kama_fast_period.low, self.kama_fast_period.high + 1):
            dataframe = CommonIndicators.add_kama(dataframe, period=p)

        for p in range(self.kama_slow_period.low, self.kama_slow_period.high + 1):
            dataframe = CommonIndicators.add_kama(dataframe, period=p)

        for p in range(self.adx_period.low, self.adx_period.high + 1):
            dataframe = CommonIndicators.add_adx(dataframe, period=p)

        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        kf = f"kama_{self.kama_fast_period.value}"
        ks = f"kama_{self.kama_slow_period.value}"
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            (dataframe[kf] > dataframe[ks])
            & (dataframe[kf].shift(1) <= dataframe[ks].shift(1))
            & (dataframe[adx_col] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        kf = f"kama_{self.kama_fast_period.value}"
        ks = f"kama_{self.kama_slow_period.value}"

        conditions = (
            (dataframe[kf] < dataframe[ks])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
