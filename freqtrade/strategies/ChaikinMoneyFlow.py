# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : ChaikinMoneyFlow
# CATÉGORIE : Volume-Weighted Momentum — Accumulation/Distribution
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. CMF > seuil (accumulation — smart money buying)
# 2. CMF vient de croiser au-dessus du seuil (signal frais)
# 3. Close > EMA fast > EMA slow (tendance haussière)
# 4. RSI entre rsi_min et rsi_max (ni survendu ni suracheté)
# 5. Volume > 0
# Sortie : CMF < -seuil (distribution) OU close < EMA fast OU RSI > rsi_exit
#
# INDICATEUR CLÉ :
# CMF = SUM(Money Flow Volume, period) / SUM(Volume, period)
# Money Flow Volume = ((close - low) - (high - close)) / (high - low) * volume
# Valeurs positives = accumulation, négatives = distribution
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import pandas_ta as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ChaikinMoneyFlow(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "180": 0.05, "480": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    cmf_period = IntParameter(10, 30, default=20, space="buy")
    cmf_threshold = DecimalParameter(0.0, 0.3, default=0.05, decimals=2, space="buy")
    ema_fast = IntParameter(10, 30, default=20, space="buy")
    ema_slow = IntParameter(30, 80, default=50, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=35, space="buy")
    rsi_max = IntParameter(60, 80, default=70, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="ChaikinMoneyFlow")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer CMF pour TOUTES les valeurs possibles (hyperopt-safe)
        for p in range(self.cmf_period.low, self.cmf_period.high + 1):
            dataframe[f"cmf_{p}"] = ta.cmf(
                dataframe["high"], dataframe["low"],
                dataframe["close"], dataframe["volume"],
                length=p,
            )

        # Pre-calculer EMA pour TOUTES les valeurs possibles (hyperopt-safe)
        all_ema_periods = set(
            list(range(self.ema_fast.low, self.ema_fast.high + 1))
            + list(range(self.ema_slow.low, self.ema_slow.high + 1))
        )
        for p in all_ema_periods:
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cmf_col = f"cmf_{self.cmf_period.value}"
        ema_f = f"ema_{self.ema_fast.value}"
        ema_s = f"ema_{self.ema_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        threshold = self.cmf_threshold.value

        conditions = (
            (dataframe[cmf_col] > threshold)                          # accumulation
            & (dataframe[cmf_col].shift(1) <= threshold)              # crossover frais
            & (dataframe["close"] > dataframe[ema_f])                 # prix > EMA fast
            & (dataframe[ema_f] > dataframe[ema_s])                   # EMA fast > EMA slow
            & (dataframe[rsi_col] > self.rsi_min.value)               # RSI pas survendu
            & (dataframe[rsi_col] < self.rsi_max.value)               # RSI pas suracheté
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cmf_col = f"cmf_{self.cmf_period.value}"
        ema_f = f"ema_{self.ema_fast.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        threshold = self.cmf_threshold.value

        conditions = (
            (dataframe[cmf_col] < -threshold)                         # distribution
            | (dataframe["close"] < dataframe[ema_f])                 # perte du support EMA
            | (dataframe[rsi_col] > self.rsi_exit.value)              # RSI suracheté
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
