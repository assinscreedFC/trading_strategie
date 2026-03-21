# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : ADOSCTrailing
# CATEGORIE : Trend+Volume — ADOSC + ATR Trailing Stop
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# L'ADOSC (Accumulation/Distribution Oscillator) mesure la pression
# acheteuse/vendeuse via le flux de volume. Quand il est positif ET
# croissant, les institutionnels accumulent.
# 1. ADOSC positif ET croissant + prix > EMA(50) → long
# 2. Sortie : ATR trailing stop (multiplicateur configurable)
# SOURCE : PyQuantLab — +65.8% annualise sur ETH
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class ADOSCTrailing(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 80

    minimal_roi = {"0": 0.15, "240": 0.08, "720": 0.04, "1440": 0.02}
    stoploss = -0.08
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    adosc_fast = IntParameter(2, 5, default=3, space="buy")
    adosc_slow = IntParameter(8, 15, default=10, space="buy")
    ema_period = IntParameter(30, 80, default=50, space="buy")
    adosc_lookback = IntParameter(1, 5, default=1, space="buy")

    # ── Sell params ──
    atr_period = IntParameter(10, 25, default=14, space="sell")
    atr_mult = IntParameter(25, 50, default=35, space="sell")  # /10 → 2.5 a 5.0

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
            self._logger = TradeLogger(strategy_name="ADOSCTrailing")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # EMA pour toutes les valeurs
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # ATR pour toutes les valeurs
        for atr_p in range(self.atr_period.low, self.atr_period.high + 1):
            dataframe = CommonIndicators.add_atr(dataframe, period=atr_p)

        # ADOSC pour toutes les combinaisons fast/slow
        for fast in range(self.adosc_fast.low, self.adosc_fast.high + 1):
            for slow in range(self.adosc_slow.low, self.adosc_slow.high + 1):
                dataframe = CommonIndicators.add_adosc(dataframe, fast=fast, slow=slow)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adosc_col = f"adosc_{self.adosc_fast.value}_{self.adosc_slow.value}"
        ema_col = f"ema_{self.ema_period.value}"
        lb = self.adosc_lookback.value

        conditions = (
            (dataframe[adosc_col] > 0)
            & (dataframe[adosc_col] > dataframe[adosc_col].shift(lb))
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adosc_col = f"adosc_{self.adosc_fast.value}_{self.adosc_slow.value}"

        # Sortie quand ADOSC devient negatif
        conditions = (
            dataframe[adosc_col] < 0
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
