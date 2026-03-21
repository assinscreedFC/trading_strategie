# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : BollingerMACDReversal
# CATEGORIE : Mean-reversion — BB + MACD Confirmation
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Combine un niveau extreme (BB lower) avec une confirmation
# de retournement de momentum (MACD histogram rising).
# 1. Close < BB lower (prix extreme bas)
# 2. MACD histogram en hausse (2 bougies)
# 3. RSI < seuil (oversold confirme)
# 4. Volume > SMA volume
# 5. Sortie : close >= BB middle OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class BollingerMACDReversal(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    bb_period = IntParameter(15, 30, default=20, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(20, 45, default=40, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

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
            self._logger = TradeLogger(strategy_name="BollingerMACDReversal")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.bb_period.low, self.bb_period.high + 1):
            dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=p)

        for p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=p)

        dataframe = CommonIndicators.add_macd(dataframe)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_lower = f"bb_lower_{self.bb_period.value}"
        bb_middle = f"bb_middle_{self.bb_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        # MACD histogram rising (1 bougie suffit — 2 bougies trop restrictif sur 3 paires 4h)
        macd_rising = (
            dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1)
        )

        # BB lower proximity (close dans les 1% de la bande basse — strict < trop rare sur 3 paires 4h)
        conditions = (
            (dataframe["close"] <= dataframe[bb_lower] * 1.01)
            & macd_rising
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_middle = f"bb_middle_{self.bb_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] >= dataframe[bb_middle])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
