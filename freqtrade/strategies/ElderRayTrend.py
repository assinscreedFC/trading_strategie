# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : ElderRayTrend
# CATÉGORIE : Trend Following — Elder Ray Index
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Elder Ray Index mesure la force des bulls et bears par rapport
# à une EMA de référence.
#   Bull Power = High - EMA(close, period)
#   Bear Power = Low  - EMA(close, period)
#
# CONDITIONS D'ENTRÉE (toutes requises) :
# 1. Close > EMA slow (tendance haussière confirmée)
# 2. EMA period en hausse (ema > ema.shift(1))
# 3. Bear Power < 0 mais en hausse (bears faiblissent)
# 4. Bull Power > 0 (bulls en contrôle)
# 5. RSI entre rsi_min et rsi_max
# 6. Volume > volume_mult * volume SMA
#
# CONDITIONS DE SORTIE :
# - Bull Power < 0 (bulls perdent le contrôle)
# - OU Bear Power en baisse (bears se renforcent)
# - OU RSI > rsi_exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ElderRayTrend(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_period = IntParameter(10, 30, default=13, space="buy")
    ema_slow = IntParameter(30, 80, default=50, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=35, space="buy")
    rsi_max = IntParameter(60, 80, default=70, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="ElderRayTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer EMA pour TOUTES les valeurs possibles (hyperopt-safe)
        all_ema_periods = set(
            list(range(self.ema_period.low, self.ema_period.high + 1))
            + list(range(self.ema_slow.low, self.ema_slow.high + 1))
        )
        for p in all_ema_periods:
            dataframe = CommonIndicators.add_ema(dataframe, period=p)

        # Bull Power et Bear Power pour chaque ema_period possible
        for p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe[f"bull_power_{p}"] = dataframe["high"] - dataframe[f"ema_{p}"]
            dataframe[f"bear_power_{p}"] = dataframe["low"] - dataframe[f"ema_{p}"]

        # RSI pour toutes les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Volume SMA pour toutes les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_p = self.ema_period.value
        ema_col = f"ema_{ema_p}"
        ema_s = f"ema_{self.ema_slow.value}"
        bull_col = f"bull_power_{ema_p}"
        bear_col = f"bear_power_{ema_p}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            # 1. Uptrend : close > EMA slow
            (dataframe["close"] > dataframe[ema_s])
            # 2. EMA period en hausse
            & (dataframe[ema_col] > dataframe[ema_col].shift(1))
            # 3. Bear Power < 0 mais en hausse (bears faiblissent)
            & (dataframe[bear_col] < 0)
            & (dataframe[bear_col] > dataframe[bear_col].shift(1))
            # 4. Bull Power > 0 (bulls en contrôle)
            & (dataframe[bull_col] > 0)
            # 5. RSI dans la zone
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            # 6. Volume suffisant
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_p = self.ema_period.value
        bull_col = f"bull_power_{ema_p}"
        bear_col = f"bear_power_{ema_p}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            # Bull Power < 0 (bulls perdent le contrôle)
            (dataframe[bull_col] < 0)
            # OU Bear Power en baisse (bears se renforcent)
            | (dataframe[bear_col] < dataframe[bear_col].shift(1))
            # OU RSI > seuil exit
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
