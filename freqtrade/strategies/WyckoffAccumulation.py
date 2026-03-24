# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : WyckoffAccumulation
# CATÉGORIE : Avancée — Wyckoff Accumulation Phase
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Détection du "Spring" Wyckoff : le prix fait un nouveau low
#    (sous le rolling min) MAIS le volume diminue (signe que la
#    pression vendeuse s'épuise) ET le prix remonte rapidement
# 2. Confirmation : RSI divergence haussière (prix lower low,
#    RSI higher low)
# 3. Sortie : prix dépasse le "Creek" (résistance = rolling max)
#    OU RSI en surachat
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class WyckoffAccumulation(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.15, "480": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.07
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    accumulation_period = IntParameter(20, 50, default=30, space="buy")
    creek_period = IntParameter(15, 30, default=20, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(25, 50, default=40, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(60, 80, default=70, space="sell")

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
            self._logger = TradeLogger(strategy_name="WyckoffAccumulation")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # Rolling min (support de la zone d'accumulation) pour TOUTES les valeurs
        for acc_p in range(self.accumulation_period.low, self.accumulation_period.high + 1):
            dataframe[f"rolling_min_{acc_p}"] = dataframe["close"].rolling(window=acc_p).min()

        # Rolling max (Creek = résistance) pour TOUTES les valeurs
        for creek_p in range(self.creek_period.low, self.creek_period.high + 1):
            dataframe[f"creek_{creek_p}"] = dataframe["high"].rolling(window=creek_p).max()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"
        rolling_min_col = f"rolling_min_{self.accumulation_period.value}"

        # Spring : prix fait un nouveau low mais volume diminue et prix remonte
        spring = (
            (dataframe["close"] < dataframe[rolling_min_col].shift(1))
            & (dataframe["volume"] < dataframe[vol_sma_col])
            & (dataframe["close"] > dataframe["low"].shift(1))
        )

        # RSI divergence : prix fait lower low mais RSI fait higher low
        price_lower_low = dataframe["close"] < dataframe["close"].shift(5)
        rsi_higher_low = dataframe[rsi_col] > dataframe[rsi_col].shift(5)
        divergence = price_lower_low & rsi_higher_low

        conditions = (
            spring
            & divergence
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        creek_col = f"creek_{self.creek_period.value}"

        # Sortie : prix dépasse le Creek (résistance) OU RSI en surachat
        conditions = (
            (dataframe["close"] > dataframe[creek_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
