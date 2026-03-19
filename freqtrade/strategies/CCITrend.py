# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : CCITrend
# CATÉGORIE : Momentum — CCI Trend Following
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# CCI (Commodity Channel Index) mesure la déviation du prix
# par rapport à sa moyenne statistique.
# 1. CCI croise au-dessus de +100 → momentum haussier fort
# 2. Close > EMA50 → confirmation de tendance
# 3. Sortie : CCI < 0 OU close < EMA20
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class CCITrend(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.08, "120": 0.04, "360": 0.02, "720": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    cci_period = IntParameter(10, 30, default=14, space="buy")
    ema_fast = IntParameter(15, 30, default=20, space="buy")
    ema_slow = IntParameter(40, 70, default=50, space="buy")
    cci_entry = IntParameter(50, 150, default=100, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    cci_exit = IntParameter(-50, 50, default=0, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="CCITrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_fast.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_slow.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        # CCI calc: (typical_price - SMA(typical_price)) / (0.015 * mean_deviation)
        period = self.cci_period.value
        typical_price = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mean_dev = typical_price.rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        dataframe["cci"] = (typical_price - sma_tp) / (0.015 * mean_dev)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_slow_col = f"ema_{self.ema_slow.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe["cci"] > self.cci_entry.value)
            & (dataframe["cci"].shift(1) <= self.cci_entry.value)
            & (dataframe["close"] > dataframe[ema_slow_col])
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast_col = f"ema_{self.ema_fast.value}"

        conditions = (
            (dataframe["cci"] < self.cci_exit.value)
            | (dataframe["close"] < dataframe[ema_fast_col])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
