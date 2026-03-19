# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : KeltnerBounce
# CATÉGORIE : Nouvelle — Mean Reversion ATR (77% WR documenté)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Keltner Channel = EMA ± multiplier * ATR
# Plus robuste que BB car utilise ATR au lieu de std dev.
# 1. Prix sous Keltner lower → survente
# 2. RSI < seuil → confirmation
# 3. Sortie : prix revient à EMA (middle) OU upper band
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class KeltnerBounce(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 50

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_period = IntParameter(10, 40, default=20, space="buy")
    atr_period = IntParameter(7, 30, default=14, space="buy")
    atr_mult = DecimalParameter(1.0, 3.5, default=2.0, decimals=1, space="buy")
    rsi_period = IntParameter(7, 30, default=14, space="buy")
    rsi_entry = IntParameter(20, 50, default=40, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 3.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(55, 85, default=65, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="KeltnerBounce")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_period.value)
        dataframe = CommonIndicators.add_atr(dataframe, period=self.atr_period.value)
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        # Keltner Channel
        ema_col = f"ema_{self.ema_period.value}"
        atr_col = f"atr_{self.atr_period.value}"
        dataframe["keltner_upper"] = dataframe[ema_col] + self.atr_mult.value * dataframe[atr_col]
        dataframe["keltner_lower"] = dataframe[ema_col] - self.atr_mult.value * dataframe[atr_col]
        dataframe["keltner_middle"] = dataframe[ema_col]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe["close"] < dataframe["keltner_lower"])
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] >= dataframe["keltner_middle"])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
