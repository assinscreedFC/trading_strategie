# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATEGIE : IchimokuBreakout
# CATEGORIE : Tendance / Ichimoku Kinko Hyo
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# Ichimoku Kinko Hyo = systeme complet qui combine tendance,
# support/resistance et momentum en un seul indicateur.
# - Tenkan-sen (conversion line) = momentum court terme
# - Kijun-sen (base line) = tendance moyen terme
# - Senkou Span A & B = nuage (Kumo) = support/resistance
#
# ENTREE :
# 1. Close au-dessus du nuage (tendance haussiere)
# 2. Tenkan > Kijun (signal haussier)
# 3. Breakout frais (close vient de passer au-dessus du nuage)
#
# SORTIE :
# Close sous le nuage OU Tenkan < Kijun
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class IchimokuBreakout(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.15, "720": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    tenkan_period = IntParameter(7, 12, default=9, space="buy")
    kijun_period = IntParameter(20, 35, default=26, space="buy")
    senkou_b_period = IntParameter(40, 65, default=52, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    exit_confirm_candles = IntParameter(1, 3, default=1, space="sell")

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
            self._logger = TradeLogger(strategy_name="IchimokuBreakout")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer Ichimoku pour TOUTES les combinaisons de periodes (hyperopt-safe)
        for tenkan_p in range(self.tenkan_period.low, self.tenkan_period.high + 1):
            col = f"tenkan_{tenkan_p}"
            dataframe[col] = (
                dataframe["high"].rolling(window=tenkan_p).max()
                + dataframe["low"].rolling(window=tenkan_p).min()
            ) / 2

        for kijun_p in range(self.kijun_period.low, self.kijun_period.high + 1):
            col = f"kijun_{kijun_p}"
            dataframe[col] = (
                dataframe["high"].rolling(window=kijun_p).max()
                + dataframe["low"].rolling(window=kijun_p).min()
            ) / 2

        for senkou_p in range(self.senkou_b_period.low, self.senkou_b_period.high + 1):
            col = f"senkou_b_{senkou_p}"
            dataframe[col] = (
                dataframe["high"].rolling(window=senkou_p).max()
                + dataframe["low"].rolling(window=senkou_p).min()
            ) / 2

        # Senkou Span A depend de tenkan + kijun — pre-calculer pour toutes les combos
        for tenkan_p in range(self.tenkan_period.low, self.tenkan_period.high + 1):
            for kijun_p in range(self.kijun_period.low, self.kijun_period.high + 1):
                col = f"senkou_a_{tenkan_p}_{kijun_p}"
                dataframe[col] = (
                    dataframe[f"tenkan_{tenkan_p}"] + dataframe[f"kijun_{kijun_p}"]
                ) / 2

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tenkan_col = f"tenkan_{self.tenkan_period.value}"
        kijun_col = f"kijun_{self.kijun_period.value}"
        senkou_a_col = f"senkou_a_{self.tenkan_period.value}_{self.kijun_period.value}"
        senkou_b_col = f"senkou_b_{self.senkou_b_period.value}"

        kumo_top = dataframe[[senkou_a_col, senkou_b_col]].max(axis=1)
        kumo_top_prev = kumo_top.shift(1)

        conditions = (
            # Close au-dessus du nuage
            (dataframe["close"] > kumo_top)
            # Tenkan > Kijun (signal haussier)
            & (dataframe[tenkan_col] > dataframe[kijun_col])
            # Breakout frais : close vient de passer au-dessus du nuage
            & (dataframe["close"].shift(1) <= kumo_top_prev)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tenkan_col = f"tenkan_{self.tenkan_period.value}"
        kijun_col = f"kijun_{self.kijun_period.value}"
        senkou_a_col = f"senkou_a_{self.tenkan_period.value}_{self.kijun_period.value}"
        senkou_b_col = f"senkou_b_{self.senkou_b_period.value}"

        kumo_bottom = dataframe[[senkou_a_col, senkou_b_col]].min(axis=1)

        conditions = (
            # Close sous le nuage
            (dataframe["close"] < kumo_bottom)
            # OU Tenkan < Kijun (tendance baissiere)
            | (dataframe[tenkan_col] < dataframe[kijun_col])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
