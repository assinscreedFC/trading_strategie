# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : WilliamsRBounce
# CATÉGORIE : Nouvelle — Mean Reversion Oscillateur
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Williams %R mesure la position du close par rapport au range.
# 1. Williams %R < -80 → zone de survente
# 2. Close > EMA rapide → confirmation du rebond
# 3. Sortie : Williams %R > -20 (suracheté) OU close < EMA mid
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class WilliamsRBounce(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 50

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    wr_period = IntParameter(7, 21, default=14, space="buy")
    ema_fast = IntParameter(5, 15, default=9, space="buy")
    ema_mid = IntParameter(15, 30, default=20, space="buy")
    wr_entry = IntParameter(-90, -70, default=-80, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    wr_exit = IntParameter(-30, -10, default=-20, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="WilliamsRBounce")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_fast.value)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_mid.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        # Williams %R calc manuelle
        wr_p = self.wr_period.value
        highest_high = dataframe["high"].rolling(window=wr_p).max()
        lowest_low = dataframe["low"].rolling(window=wr_p).min()
        dataframe["williams_r"] = ((highest_high - dataframe["close"]) / (highest_high - lowest_low)) * -100

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_f = f"ema_{self.ema_fast.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe["williams_r"] < self.wr_entry.value)
            & (dataframe["close"] > dataframe[ema_f])
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_m = f"ema_{self.ema_mid.value}"

        conditions = (
            (dataframe["williams_r"] > self.wr_exit.value)
            | (dataframe["close"] < dataframe[ema_m])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
