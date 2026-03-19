# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : EMACrossADXFilter
# CATEGORIE : Tendance / EMA Cross + ADX Filter
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Simple croisement EMA (fast/slow) avec filtre ADX pour ne
# trader que quand la tendance est forte. Les EMA crosses sans
# filtre generent beaucoup de faux signaux en range — l'ADX
# elimine ces signaux parasites en exigeant une tendance forte.
#
# ENTREE :
# 1. EMA fast > EMA slow (cross haussier)
# 2. EMA fast.shift(1) <= EMA slow.shift(1) (croisement frais)
# 3. ADX > 25 (tendance forte)
# 4. Close > EMA slow (au-dessus de la tendance)
# 5. Volume > N fois la moyenne (confirmation)
#
# SORTIE :
# EMA fast < EMA slow (cross baissier) OU ADX < 20 (tendance faiblit)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class EMACrossADXFilter(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    ema_fast = IntParameter(5, 20, default=12, space="buy")
    ema_slow = IntParameter(20, 60, default=26, space="buy")
    adx_period = IntParameter(7, 21, default=14, space="buy")
    adx_entry = IntParameter(15, 35, default=25, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # ── Sell params ──
    adx_exit = IntParameter(10, 25, default=20, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="EMACrossADXFilter")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer EMA fast pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_fast.low, self.ema_fast.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer EMA slow pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_slow.low, self.ema_slow.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer ADX pour TOUTES les valeurs possibles
        for adx_p in range(self.adx_period.low, self.adx_period.high + 1):
            dataframe = CommonIndicators.add_adx(dataframe, period=adx_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast_col = f"ema_{self.ema_fast.value}"
        ema_slow_col = f"ema_{self.ema_slow.value}"
        adx_col = f"adx_{self.adx_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"

        conditions = (
            # EMA cross haussier
            (dataframe[ema_fast_col] > dataframe[ema_slow_col])
            # Croisement frais (vient de se produire)
            & (dataframe[ema_fast_col].shift(1) <= dataframe[ema_slow_col].shift(1))
            # ADX indique une tendance forte
            & (dataframe[adx_col] > self.adx_entry.value)
            # Close au-dessus de la tendance
            & (dataframe["close"] > dataframe[ema_slow_col])
            # Volume confirme
            & (dataframe["volume"] > self.volume_mult.value * dataframe[vol_sma_col])
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast_col = f"ema_{self.ema_fast.value}"
        ema_slow_col = f"ema_{self.ema_slow.value}"
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            # EMA cross baissier
            (dataframe[ema_fast_col] < dataframe[ema_slow_col])
            # OU tendance faiblit
            | (dataframe[adx_col] < self.adx_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
