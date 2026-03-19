# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : RSIMomentumTrend
# CATÉGORIE : Momentum — RSI comme indicateur de tendance
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. RSI utilisé comme indicateur de MOMENTUM (pas mean reversion)
#    RSI > 50 = momentum haussier, RSI < 50 = momentum baissier
# 2. Entrée : RSI croise au-dessus de 50 + close > EMA50 (tendance
#    haussière) + MACD histogram > 0 + volume > moyenne
# 3. Sortie : RSI croise sous 50 OU MACD histogram négatif et
#    décroissant depuis 2 bougies
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class RSIMomentumTrend(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    ema_period = IntParameter(30, 70, default=50, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, space="buy")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="RSIMomentumTrend")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer EMA pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # MACD (paramètres fixes 12/26/9)
        dataframe = CommonIndicators.add_macd(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"

        # RSI cross above 50 : RSI > 50 et RSI précédent <= 50
        rsi_cross_above_50 = (
            (dataframe[rsi_col] > 50)
            & (dataframe[rsi_col].shift(1) <= 50)
        )

        conditions = (
            rsi_cross_above_50
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["macd_histogram"] > 0)
            & (dataframe["volume"] > dataframe[vol_sma_col] * self.volume_mult.value)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        # RSI cross below 50
        rsi_cross_below_50 = dataframe[rsi_col] < 50

        # MACD histogram négatif et décroissant depuis 2 bougies
        macd_declining = (
            (dataframe["macd_histogram"] < 0)
            & (dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1))
        )

        conditions = rsi_cross_below_50 | macd_declining

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
