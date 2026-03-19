# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : MACDDivergence
# CATÉGORIE : Divergence — MACD Divergence Haussière
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Divergence haussière MACD : le prix fait un lower low mais
#    le MACD histogram fait un higher low → signal de retournement
# 2. Entrée : prix lower low sur N bougies + MACD histogram higher
#    low + RSI en zone basse (< 45) + volume > 0.8x moyenne
# 3. Sortie : MACD histogram négatif et décroissant depuis 3 bougies
#    OU RSI > 70
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MACDDivergence(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.12, "480": 0.06, "1440": 0.03}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    lookback = IntParameter(3, 15, default=5, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(30, 55, default=45, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=0.8, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="MACDDivergence")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # MACD (paramètres fixes 12/26/9)
        dataframe = CommonIndicators.add_macd(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"
        lb = self.lookback.value

        # Divergence haussière : prix lower low + MACD histogram higher low
        price_lower_low = dataframe["close"] < dataframe["close"].shift(lb)
        macd_higher_low = dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(lb)

        conditions = (
            price_lower_low
            & macd_higher_low
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > dataframe[vol_sma_col] * self.volume_mult.value)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        # MACD histogram négatif et décroissant depuis 3 bougies
        macd_declining_3 = (
            (dataframe["macd_histogram"] < 0)
            & (dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1))
            & (dataframe["macd_histogram"].shift(1) < dataframe["macd_histogram"].shift(2))
        )

        conditions = macd_declining_3 | (dataframe[rsi_col] > self.rsi_exit.value)

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
