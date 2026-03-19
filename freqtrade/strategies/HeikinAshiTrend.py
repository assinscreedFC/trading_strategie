# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : HeikinAshiTrend
# CATÉGORIE : Tendance — Heikin Ashi Momentum
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Heikin Ashi lisse le bruit des chandeliers classiques pour
# identifier les tendances fortes.
# 1. Bougie HA verte + pas de mèche basse → tendance haussière forte
# 2. EMA50 en hausse → confirmation
# 3. Sortie : bougie HA rouge sans mèche haute OU ha_close < EMA50
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class HeikinAshiTrend(IStrategy):
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
    ema_period = IntParameter(30, 70, default=50, space="buy")
    lookback = IntParameter(1, 5, default=2, space="buy")
    wick_tolerance = DecimalParameter(0.0001, 0.005, default=0.001, decimals=4, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="HeikinAshiTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_period.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        # Heikin Ashi calc
        dataframe["ha_close"] = (
            dataframe["open"] + dataframe["high"] + dataframe["low"] + dataframe["close"]
        ) / 4

        ha_open = dataframe["ha_close"].copy()
        ha_open.iloc[0] = (dataframe["open"].iloc[0] + dataframe["close"].iloc[0]) / 2
        for i in range(1, len(dataframe)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + dataframe["ha_close"].iloc[i - 1]) / 2
        dataframe["ha_open"] = ha_open

        dataframe["ha_high"] = dataframe[["high", "ha_open", "ha_close"]].max(axis=1)
        dataframe["ha_low"] = dataframe[["low", "ha_open", "ha_close"]].min(axis=1)

        # EMA rising check
        ema_col = f"ema_{self.ema_period.value}"
        dataframe["ema_rising"] = dataframe[ema_col] > dataframe[ema_col].shift(self.lookback.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tol = self.wick_tolerance.value

        # HA green + no lower wick (with tolerance) + EMA rising
        conditions = (
            (dataframe["ha_close"] > dataframe["ha_open"])
            & (
                (dataframe["ha_low"] - dataframe["ha_open"]).abs()
                < tol * dataframe["ha_close"]
            )
            & (dataframe["ema_rising"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f"ema_{self.ema_period.value}"
        tol = self.wick_tolerance.value

        # HA red + no upper wick (with tolerance) OR ha_close < EMA
        conditions = (
            (
                (dataframe["ha_close"] < dataframe["ha_open"])
                & (
                    (dataframe["ha_high"] - dataframe["ha_close"]).abs()
                    < tol * dataframe["ha_close"]
                )
            )
            | (dataframe["ha_close"] < dataframe[ema_col])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
