# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ElderImpulse
# CATEGORIE : Momentum+Trend — Elder Impulse System
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Combine EMA et MACD histogram pour classifier chaque barre :
# - Vert : EMA montante ET MACD histo montant → momentum haussier
# - Rouge : EMA descendante ET MACD histo descendant → momentum baissier
# - Bleu : mixte → neutre
# 1. Premier bar vert apres bleu/rouge → long
# 2. Bar rouge → exit
# NOTE : Different de ElderRayTrend (deja teste, overfit)
# SOURCE : Alexander Elder — Trading for a Living
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ElderImpulse(IStrategy):
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
    ema_period = IntParameter(8, 20, default=13, space="buy")
    macd_fast = IntParameter(8, 16, default=12, space="buy")
    macd_slow = IntParameter(20, 30, default=26, space="buy")
    macd_signal = IntParameter(7, 12, default=9, space="buy")

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
            self._logger = TradeLogger(strategy_name="ElderImpulse")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # EMA pour toutes les valeurs
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # MACD — une seule version car les params sont lies
        dataframe = CommonIndicators.add_macd(
            dataframe,
            fast=self.macd_fast.value,
            slow=self.macd_slow.value,
            signal=self.macd_signal.value,
        )

        # Classification des barres
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            ema_col = f"ema_{ema_p}"
            ema_rising = dataframe[ema_col] > dataframe[ema_col].shift(1)
            ema_falling = dataframe[ema_col] < dataframe[ema_col].shift(1)
            macd_rising = dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1)
            macd_falling = dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1)

            # 1 = vert, -1 = rouge, 0 = bleu
            dataframe[f"impulse_{ema_p}"] = 0
            dataframe.loc[ema_rising & macd_rising, f"impulse_{ema_p}"] = 1
            dataframe.loc[ema_falling & macd_falling, f"impulse_{ema_p}"] = -1

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        impulse_col = f"impulse_{self.ema_period.value}"

        # Premier bar vert apres un non-vert
        conditions = (
            (dataframe[impulse_col] == 1)
            & (dataframe[impulse_col].shift(1) != 1)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        impulse_col = f"impulse_{self.ema_period.value}"

        # Bar rouge → sortie
        conditions = (
            dataframe[impulse_col] == -1
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
