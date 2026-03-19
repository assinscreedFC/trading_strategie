# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : MultiTimeframeMomentum
# CATEGORIE : Multi-Timeframe / Momentum
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Aligner le momentum sur 2 timeframes pour des entrees
# a haute probabilite :
# - 4h (HTF) : definit la tendance principale via triple EMA
#   (EMA9 > EMA21 > EMA50 = tendance haussiere confirmee)
# - 1h (LTF) : entree sur pullback vers EMA20 quand le RSI
#   est en zone neutre/basse et une bougie verte confirme
#
# ENTREE :
# 1. 4h : EMA fast > EMA mid > EMA slow (tendance haussiere HTF)
# 2. 1h : close pullback vers EMA20 (close entre 99% et 101% de EMA)
# 3. RSI entre 35 et 55 (zone de pullback, pas de surachat)
# 4. Bougie verte (close > open) = rebond confirme
#
# SORTIE :
# 4h EMA fast < EMA mid (trend casse sur HTF) OU 1h RSI > 75
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter
from freqtrade.strategy import merge_informative_pair

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MultiTimeframeMomentum(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 200

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params (4h) ──
    ema_fast_4h = IntParameter(5, 15, default=9, space="buy")
    ema_mid_4h = IntParameter(15, 30, default=21, space="buy")
    ema_slow_4h = IntParameter(40, 60, default=50, space="buy")

    # ── Buy params (1h) ──
    ema_pullback_1h = IntParameter(15, 30, default=20, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(25, 45, default=35, space="buy")
    rsi_max = IntParameter(45, 65, default=55, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="MultiTimeframeMomentum")
            self._notifier = TelegramNotifier()

    def informative_pairs(self):
        return [(pair, "4h") for pair in self.dp.current_whitelist()]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        pair = metadata["pair"]

        # ── 4h indicators ──
        informative_4h = self.dp.get_pair_dataframe(pair, "4h")

        # Pre-calculer EMA 4h pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_fast_4h.low, self.ema_fast_4h.high + 1):
            informative_4h = CommonIndicators.add_ema(informative_4h, period=ema_p)
        for ema_p in range(self.ema_mid_4h.low, self.ema_mid_4h.high + 1):
            informative_4h = CommonIndicators.add_ema(informative_4h, period=ema_p)
        for ema_p in range(self.ema_slow_4h.low, self.ema_slow_4h.high + 1):
            informative_4h = CommonIndicators.add_ema(informative_4h, period=ema_p)

        dataframe = merge_informative_pair(
            dataframe, informative_4h, self.timeframe, "4h", ffill=True
        )

        # ── 1h indicators ──
        # Pre-calculer EMA 1h pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_pullback_1h.low, self.ema_pullback_1h.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer RSI pour TOUTES les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast_col = f"ema_{self.ema_fast_4h.value}_4h"
        ema_mid_col = f"ema_{self.ema_mid_4h.value}_4h"
        ema_slow_col = f"ema_{self.ema_slow_4h.value}_4h"
        ema_pullback_col = f"ema_{self.ema_pullback_1h.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            # 4h : triple EMA alignee (tendance haussiere)
            (dataframe[ema_fast_col] > dataframe[ema_mid_col])
            & (dataframe[ema_mid_col] > dataframe[ema_slow_col])
            # 1h : pullback vers EMA (close entre 99% et 101%)
            & (dataframe["close"] < dataframe[ema_pullback_col] * 1.01)
            & (dataframe["close"] > dataframe[ema_pullback_col] * 0.99)
            # RSI en zone de pullback
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            # Bougie verte (rebond confirme)
            & (dataframe["close"] > dataframe["open"])
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast_col = f"ema_{self.ema_fast_4h.value}_4h"
        ema_mid_col = f"ema_{self.ema_mid_4h.value}_4h"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            # 4h : trend casse (EMA fast < EMA mid)
            (dataframe[ema_fast_col] < dataframe[ema_mid_col])
            # OU RSI en surachat
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
