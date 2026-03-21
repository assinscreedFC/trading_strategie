# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : OBVTrendConfirm
# CATEGORIE : Volume-trend — OBV Accumulation Confirmee
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# OBV (On-Balance Volume) precede le prix de 2-5 bougies (Granville).
# 1. OBV > OBV_SMA (accumulation en cours)
# 2. OBV rising sur N bougies (momentum volume)
# 3. EMA trend filter + RSI pas en surachat
# 4. Sortie : OBV < OBV_SMA (distribution)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class OBVTrendConfirm(IStrategy):
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
    obv_sma_period = IntParameter(10, 30, default=20, space="buy")
    obv_rising = IntParameter(2, 6, default=3, space="buy")
    ema_period = IntParameter(30, 70, default=50, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_max = IntParameter(60, 75, default=70, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 80, default=75, space="sell")

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
            self._logger = TradeLogger(strategy_name="OBVTrendConfirm")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for p in range(self.obv_sma_period.low, self.obv_sma_period.high + 1):
            dataframe = CommonIndicators.add_obv(dataframe, sma_period=p)

        for p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        for p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        obv_sma_col = f"obv_sma_{self.obv_sma_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        rising_n = self.obv_rising.value

        # OBV rising pendant N bougies
        obv_up = dataframe["obv"] > dataframe["obv"].shift(1)
        for i in range(2, rising_n + 1):
            obv_up = obv_up & (dataframe["obv"].shift(i - 1) > dataframe["obv"].shift(i))

        conditions = (
            (dataframe["obv"] > dataframe[obv_sma_col])
            & obv_up
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        obv_sma_col = f"obv_sma_{self.obv_sma_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["obv"] < dataframe[obv_sma_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
