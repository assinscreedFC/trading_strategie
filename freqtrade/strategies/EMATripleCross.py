# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : EMATripleCross
# CATÉGORIE : Nouvelle — Trend Following Conservative
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. EMA fast > EMA mid > EMA slow (alignement haussier)
# 2. EMA fast vient de croiser au-dessus de EMA mid
# 3. RSI entre 40 et 70 (ni survendu ni suracheté)
# 4. Volume > multiplicateur * moyenne
# 5. Sortie : EMA fast < EMA mid OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class EMATripleCross(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_fast = IntParameter(5, 15, default=9, space="buy")
    ema_mid = IntParameter(15, 35, default=21, space="buy")
    ema_slow = IntParameter(40, 80, default=50, space="buy")
    rsi_period = IntParameter(7, 30, default=14, space="buy")
    rsi_min = IntParameter(30, 50, default=40, space="buy")
    rsi_max = IntParameter(60, 80, default=70, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.2, decimals=1, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

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
            self._logger = TradeLogger(strategy_name="EMATripleCross")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()
        # Pre-calculer EMA pour TOUTES les valeurs possibles (hyperopt-safe)
        all_ema_periods = set(
            list(range(self.ema_fast.low, self.ema_fast.high + 1))
            + list(range(self.ema_mid.low, self.ema_mid.high + 1))
            + list(range(self.ema_slow.low, self.ema_slow.high + 1))
        )
        for p in all_ema_periods:
            dataframe = CommonIndicators.add_ema(dataframe, period=p)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_f = f"ema_{self.ema_fast.value}"
        ema_m = f"ema_{self.ema_mid.value}"
        ema_s = f"ema_{self.ema_slow.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        conditions = (
            (dataframe[ema_f] > dataframe[ema_m])
            & (dataframe[ema_m] > dataframe[ema_s])
            & (dataframe[ema_f].shift(1) <= dataframe[ema_m].shift(1))  # crossover frais
            & (dataframe[rsi_col] > self.rsi_min.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_f = f"ema_{self.ema_fast.value}"
        ema_m = f"ema_{self.ema_mid.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe[ema_f] < dataframe[ema_m])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
