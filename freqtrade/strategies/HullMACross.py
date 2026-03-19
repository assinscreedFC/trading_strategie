# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : HullMACross
# CATÉGORIE : Trend Following — Hull Moving Average Crossover
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Hull MA est plus rapide et moins en retard que l'EMA classique
#    Formule : HMA(n) = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
# 2. HMA fast croise au-dessus de HMA slow (signal haussier)
# 3. RSI entre rsi_min et rsi_max (filtre momentum)
# 4. Volume > multiplicateur * moyenne volume (confirmation)
# 5. Sortie : HMA fast < HMA slow OU RSI > seuil exit
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


class HullMACross(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "240": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    hma_fast = IntParameter(5, 20, default=9, space="buy")
    hma_slow = IntParameter(20, 60, default=21, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=40, space="buy")
    rsi_max = IntParameter(60, 80, default=70, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.2, decimals=1, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="HullMACross")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer HMA pour TOUTES les valeurs possibles (hyperopt-safe)
        all_hma_periods = set(
            list(range(self.hma_fast.low, self.hma_fast.high + 1))
            + list(range(self.hma_slow.low, self.hma_slow.high + 1))
        )
        for p in all_hma_periods:
            dataframe[f"hma_{p}"] = ta.hma(dataframe["close"], length=p)

        # Pre-calculer RSI pour toutes les valeurs possibles
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer Volume SMA pour toutes les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        hma_f = f"hma_{self.hma_fast.value}"
        hma_s = f"hma_{self.hma_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe[hma_f] > dataframe[hma_s])
            & (dataframe[hma_f].shift(1) <= dataframe[hma_s].shift(1))  # crossover frais
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        hma_f = f"hma_{self.hma_fast.value}"
        hma_s = f"hma_{self.hma_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe[hma_f] < dataframe[hma_s])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
