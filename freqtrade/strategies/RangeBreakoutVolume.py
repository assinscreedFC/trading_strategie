# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : RangeBreakoutVolume
# CATEGORIE : Breakout / Volume
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 70% du temps le marche est en range (consolidation).
# Cette strategie detecte les phases de compression via la
# largeur des Bollinger Bands (BB width < percentile 25% sur
# 100 periodes), puis trade le breakout haussier confirme par :
# 1. Close > BB upper (breakout haussier)
# 2. Volume > N fois la moyenne (confirmation par le volume)
# 3. ADX > seuil (debut de tendance)
# 4. Close > EMA (filtre de tendance)
# Sortie : close < EMA OU ADX < seuil (fin de tendance)
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class RangeBreakoutVolume(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 150

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    bb_period = IntParameter(15, 30, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")
    ema_period = IntParameter(15, 30, default=20, space="buy")
    adx_period = IntParameter(7, 21, default=14, space="buy")
    adx_entry = IntParameter(15, 30, default=20, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")

    # ── Sell params ──
    adx_exit = IntParameter(10, 20, default=15, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="RangeBreakoutVolume")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer BB pour TOUTES les valeurs de bb_period (std fixe a 2.0 pour eviter explosion combinatoire)
        for bb_p in range(self.bb_period.low, self.bb_period.high + 1):
            dataframe = CommonIndicators.add_bollinger_bands(dataframe, period=bb_p, std_dev=2.0)
            # BB width = (upper - lower) / middle — mesure la compression
            dataframe[f"bb_width_{bb_p}"] = (
                (dataframe[f"bb_upper_{bb_p}"] - dataframe[f"bb_lower_{bb_p}"])
                / dataframe[f"bb_middle_{bb_p}"]
            )
            # Percentile 25% sur 100 periodes pour detecter la compression
            dataframe[f"bb_width_pct25_{bb_p}"] = (
                dataframe[f"bb_width_{bb_p}"].rolling(window=100).quantile(0.25)
            )

        # Pre-calculer EMA pour TOUTES les valeurs possibles
        for ema_p in range(self.ema_period.low, self.ema_period.high + 1):
            dataframe = CommonIndicators.add_ema(dataframe, period=ema_p)

        # Pre-calculer ADX pour TOUTES les valeurs possibles
        for adx_p in range(self.adx_period.low, self.adx_period.high + 1):
            dataframe = CommonIndicators.add_adx(dataframe, period=adx_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_p = self.bb_period.value
        ema_col = f"ema_{self.ema_period.value}"
        adx_col = f"adx_{self.adx_period.value}"
        vol_sma_col = f"volume_sma_{self.volume_period.value}"

        # Compression detectee : BB width < percentile 25%
        compression = dataframe[f"bb_width_{bb_p}"] < dataframe[f"bb_width_pct25_{bb_p}"]

        conditions = (
            compression
            & (dataframe["close"] > dataframe[f"bb_upper_{bb_p}"])
            & (dataframe["volume"] > self.volume_mult.value * dataframe[vol_sma_col])
            & (dataframe[adx_col] > self.adx_entry.value)
            & (dataframe["close"] > dataframe[ema_col])
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f"ema_{self.ema_period.value}"
        adx_col = f"adx_{self.adx_period.value}"

        conditions = (
            (dataframe["close"] < dataframe[ema_col])
            | (dataframe[adx_col] < self.adx_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
