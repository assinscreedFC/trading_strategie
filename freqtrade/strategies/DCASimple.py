# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : DCASimple
# CATEGORIE : Baseline — Dollar Cost Averaging (achat regulier)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class DCASimple(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 50

    minimal_roi = {"0": 0.15, "720": 0.08, "1440": 0.04}
    stoploss = -0.10
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    dca_interval = IntParameter(6, 42, default=30, space="buy")

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
            self._logger = TradeLogger(strategy_name="DCASimple")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        # Pas d'indicateurs techniques — DCA pur
        # Ajouter un index sequentiel pour le modulo
        dataframe["candle_index"] = np.arange(len(dataframe))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        interval = self.dca_interval.value

        conditions = (
            (dataframe["candle_index"] % interval == 0)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Pas de signal de sortie actif — on laisse le trailing stop gerer
        dataframe["exit_long"] = 0
        return dataframe
