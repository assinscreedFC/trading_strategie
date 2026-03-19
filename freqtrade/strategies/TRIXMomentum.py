# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : TRIXMomentum
# CATÉGORIE : Momentum — Triple EMA Rate of Change
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# TRIX est le taux de changement d'une triple EMA, filtrant
# efficacement le bruit du marché.
# 1. TRIX > 0 + croisement au-dessus de la ligne signal → momentum
# 2. Close > EMA50 → confirmation de tendance
# 3. Sortie : TRIX < signal OU TRIX < 0
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class TRIXMomentum(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.08, "120": 0.04, "360": 0.02, "720": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    trix_period = IntParameter(10, 20, default=15, space="buy")
    signal_period = IntParameter(5, 15, default=9, space="buy")
    ema_period = IntParameter(30, 70, default=50, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="TRIXMomentum")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calc EMA pour TOUTES les valeurs possibles (hyperopt-safe)
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calc volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # Pre-calc TRIX pour TOUTES les valeurs de trix_period
        for trix_p in range(self.trix_period.low, self.trix_period.high + 1):
            ema1 = dataframe["close"].ewm(span=trix_p, adjust=False).mean()
            ema2 = ema1.ewm(span=trix_p, adjust=False).mean()
            ema3 = ema2.ewm(span=trix_p, adjust=False).mean()
            dataframe[f"trix_{trix_p}"] = 100 * (ema3 - ema3.shift(1)) / ema3.shift(1)

            # Pre-calc signal line pour TOUTES les combos trix_period x signal_period
            for sig_p in range(self.signal_period.low, self.signal_period.high + 1):
                dataframe[f"trix_signal_{trix_p}_{sig_p}"] = (
                    dataframe[f"trix_{trix_p}"].ewm(span=sig_p, adjust=False).mean()
                )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f"ema_{self.ema_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"
        trix_col = f"trix_{self.trix_period.value}"
        trix_sig_col = f"trix_signal_{self.trix_period.value}_{self.signal_period.value}"

        # TRIX > 0 + TRIX crosses above signal + close > EMA
        conditions = (
            (dataframe[trix_col] > 0)
            & (dataframe[trix_col] > dataframe[trix_sig_col])
            & (dataframe[trix_col].shift(1) <= dataframe[trix_sig_col].shift(1))
            & (dataframe["close"] > dataframe[ema_col])
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trix_col = f"trix_{self.trix_period.value}"
        trix_sig_col = f"trix_signal_{self.trix_period.value}_{self.signal_period.value}"

        # TRIX < signal OR TRIX < 0
        conditions = (
            (dataframe[trix_col] < dataframe[trix_sig_col])
            | (dataframe[trix_col] < 0)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
