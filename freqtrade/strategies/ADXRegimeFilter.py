# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ADXRegimeFilter
# CATEGORIE : Regime Switching — ADX Trend/Mean-Reversion
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Utilise l'ADX pour detecter le regime de marche et adapter la strategie :
# - ADX > trend_threshold : marche en tendance → entree EMA cross
# - ADX < range_threshold : marche en range → entree RSI oversold
# - Zone grise : pas de trade
# SOURCE : Concept classique de regime switching simplifie
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ADXRegimeFilter(IStrategy):
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
    adx_period = IntParameter(10, 20, default=14, space="buy")
    trend_threshold = IntParameter(20, 35, default=25, space="buy")
    range_threshold = IntParameter(15, 25, default=20, space="buy")
    ema_fast = IntParameter(8, 20, default=12, space="buy")
    ema_slow = IntParameter(20, 50, default=26, space="buy")
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(20, 40, default=30, space="buy")

    # ── Sell params ──
    rsi_overbought = IntParameter(65, 85, default=70, space="sell")

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
            self._logger = TradeLogger(strategy_name="ADXRegimeFilter")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # ADX
        for adx_p in range(self.adx_period.low, self.adx_period.high + 1):
            dataframe = CommonIndicators.add_adx(dataframe, period=adx_p)

        # EMA fast/slow
        for ema_p in range(self.ema_fast.low, self.ema_slow.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # RSI
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adx_col = f"adx_{self.adx_period.value}"
        ema_fast_col = f"ema_{self.ema_fast.value}"
        ema_slow_col = f"ema_{self.ema_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        # Mode tendance : ADX > seuil → EMA cross
        trend_entry = (
            (dataframe[adx_col] > self.trend_threshold.value)
            & (dataframe[ema_fast_col] > dataframe[ema_slow_col])
            & (dataframe[ema_fast_col].shift(1) <= dataframe[ema_slow_col].shift(1))
            & (dataframe["volume"] > 0)
        )

        # Mode range : ADX < seuil → RSI oversold
        range_entry = (
            (dataframe[adx_col] < self.range_threshold.value)
            & (dataframe[rsi_col] < self.rsi_oversold.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[trend_entry | range_entry, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adx_col = f"adx_{self.adx_period.value}"
        ema_fast_col = f"ema_{self.ema_fast.value}"
        ema_slow_col = f"ema_{self.ema_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        # Sortie tendance : EMA cross inverse
        trend_exit = (
            (dataframe[adx_col] > self.trend_threshold.value)
            & (dataframe[ema_fast_col] < dataframe[ema_slow_col])
        )

        # Sortie range : RSI overbought
        range_exit = (
            (dataframe[adx_col] < self.range_threshold.value)
            & (dataframe[rsi_col] > self.rsi_overbought.value)
        )

        dataframe.loc[trend_exit | range_exit, "exit_long"] = 1
        return dataframe
