# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : VWMASMACross
# CATEGORIE : Volume-Confirmed Trend — VWMA vs SMA Cross
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# VWMA > SMA signifie que le prix moyen pondere par volume est
# superieur au prix moyen simple → les gros volumes poussent le prix
# vers le haut = accumulation institutionnelle.
# 1. VWMA(20) cross au-dessus SMA(20) + volume > SMA(20) volume → long
# 2. Sortie : VWMA cross sous SMA
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class VWMASMACross(IStrategy):
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
    ma_period = IntParameter(10, 30, default=20, space="buy")
    volume_period = IntParameter(10, 30, default=20, space="buy")

    # ── Sell params ──
    # (pas de params sell specifiques, sortie sur cross inverse)

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
            self._logger = TradeLogger(strategy_name="VWMASMACross")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        for ma_p in range(self.ma_period.low, self.ma_period.high + 1):
            dataframe = CommonIndicators.add_vwma(dataframe, period=ma_p)
            dataframe = CommonIndicators.add_sma(dataframe, period=ma_p)

        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vwma_col = f"vwma_{self.ma_period.value}"
        sma_col = f"sma_{self.ma_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"

        conditions = (
            (dataframe[vwma_col] > dataframe[sma_col])
            & (dataframe[vwma_col].shift(1) <= dataframe[sma_col].shift(1))  # Cross
            & (dataframe["volume"] > dataframe[vol_sma_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        vwma_col = f"vwma_{self.ma_period.value}"
        sma_col = f"sma_{self.ma_period.value}"

        conditions = (
            (dataframe[vwma_col] < dataframe[sma_col])
            & (dataframe[vwma_col].shift(1) >= dataframe[sma_col].shift(1))
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
