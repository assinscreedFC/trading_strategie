# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : DonchianTurtle
# CATÉGORIE : Nouvelle — Breakout Classique (Turtle Trading)
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Inspirée de la stratégie Turtle Trading de Richard Dennis.
# 1. Entrée : close casse au-dessus du Donchian upper (N périodes)
# 2. Sortie : close casse en-dessous du Donchian lower court (M périodes)
# 3. Filtre volume optionnel pour confirmer le breakout
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class DonchianTurtle(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 50

    minimal_roi = {"0": 0.15, "720": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    entry_period = IntParameter(10, 30, default=20, space="buy")
    exit_period = IntParameter(5, 15, default=10, space="buy")
    atr_period = IntParameter(14, 50, default=30, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="DonchianTurtle")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        dataframe = CommonIndicators.add_atr(dataframe, period=self.atr_period.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=self.volume_period.value)

        # Donchian Channel calc manuelle
        entry_p = self.entry_period.value
        exit_p = self.exit_period.value

        # Canal d'entrée (long) : plus haut / plus bas sur N périodes
        dataframe[f"donchian_upper_{entry_p}"] = dataframe["high"].rolling(window=entry_p).max()
        dataframe[f"donchian_lower_{entry_p}"] = dataframe["low"].rolling(window=entry_p).min()

        # Canal de sortie (court) : plus bas sur M périodes
        dataframe[f"donchian_exit_lower_{exit_p}"] = dataframe["low"].rolling(window=exit_p).min()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        entry_p = self.entry_period.value
        vol_col = f"volume_ratio_{self.volume_period.value}"
        upper_col = f"donchian_upper_{entry_p}"

        conditions = (
            (dataframe["close"] > dataframe[upper_col].shift(1))
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_p = self.exit_period.value
        lower_col = f"donchian_exit_lower_{exit_p}"

        conditions = (
            dataframe["close"] < dataframe[lower_col].shift(1)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
