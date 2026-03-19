# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : MomentumSqueeze
# CATÉGORIE : Volatility Breakout — TTM Squeeze
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Squeeze detection : Bollinger Bands à l'intérieur du Keltner Channel
#    (compression de volatilité = marché en attente d'un mouvement)
# 2. Squeeze release : la squeeze était active récemment mais vient de
#    se relâcher (BB repassent à l'extérieur du KC)
# 3. Breakout haussier : close > BB upper (cassure par le haut)
# 4. Momentum positif : close > close N périodes avant
# 5. Volume confirmé : volume > multiplicateur * moyenne volume
# 6. Filtre RSI : pas d'achat en zone surachetée
# 7. Sortie : close < BB middle OU RSI > seuil exit
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class MomentumSqueeze(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "120": 0.05, "360": 0.02}
    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ── Buy params : Bollinger Bands ──
    bb_period = IntParameter(15, 30, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")

    # ── Buy params : Keltner Channel ──
    kc_period = IntParameter(15, 30, default=20, space="buy")
    kc_mult = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="buy")

    # ── Buy params : Squeeze ──
    squeeze_lookback = IntParameter(1, 5, default=3, space="buy")

    # ── Buy params : Momentum ──
    momentum_period = IntParameter(5, 20, default=10, space="buy")

    # ── Buy params : Volume ──
    volume_period = IntParameter(10, 50, default=20, space="buy")
    volume_mult = DecimalParameter(0.8, 3.0, default=1.2, decimals=1, space="buy")

    # ── Buy params : RSI filter ──
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_max = IntParameter(60, 80, default=75, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(70, 90, default=80, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="MomentumSqueeze")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # ── RSI pour toutes les périodes possibles ──
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # ── Volume SMA pour toutes les périodes possibles ──
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # ── Bollinger Bands : toutes les combinaisons period x std ──
        all_bb_stds = [
            round(self.bb_std.low + i * 0.1, 1)
            for i in range(int(round((self.bb_std.high - self.bb_std.low) / 0.1)) + 1)
        ]
        for bp in range(self.bb_period.low, self.bb_period.high + 1):
            sma = dataframe["close"].rolling(window=bp).mean()
            std = dataframe["close"].rolling(window=bp).std()
            for bs in all_bb_stds:
                dataframe[f"bb_upper_{bp}_{bs}"] = sma + bs * std
                dataframe[f"bb_middle_{bp}_{bs}"] = sma
                dataframe[f"bb_lower_{bp}_{bs}"] = sma - bs * std

        # ── Keltner Channel : toutes les combinaisons period x mult ──
        # EMA pour toutes les périodes KC possibles
        all_kc_periods = set(range(self.kc_period.low, self.kc_period.high + 1))
        for kp in all_kc_periods:
            dataframe = CommonIndicators.add_ema(dataframe, period=kp)
            dataframe = CommonIndicators.add_atr(dataframe, period=kp)

        all_kc_mults = [
            round(self.kc_mult.low + i * 0.1, 1)
            for i in range(int(round((self.kc_mult.high - self.kc_mult.low) / 0.1)) + 1)
        ]
        for kp in all_kc_periods:
            ema_col = f"ema_{kp}"
            atr_col = f"atr_{kp}"
            for km in all_kc_mults:
                dataframe[f"kc_upper_{kp}_{km}"] = dataframe[ema_col] + km * dataframe[atr_col]
                dataframe[f"kc_lower_{kp}_{km}"] = dataframe[ema_col] - km * dataframe[atr_col]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bp = self.bb_period.value
        bs = self.bb_std.value
        kp = self.kc_period.value
        km = self.kc_mult.value
        lookback = self.squeeze_lookback.value
        mom_p = self.momentum_period.value
        rsi_col = f"rsi_{self.rsi_period.value}"
        vol_col = f"volume_ratio_{self.volume_period.value}"

        bb_upper = dataframe[f"bb_upper_{bp}_{bs}"]
        bb_lower = dataframe[f"bb_lower_{bp}_{bs}"]
        bb_middle = dataframe[f"bb_middle_{bp}_{bs}"]
        kc_upper = dataframe[f"kc_upper_{kp}_{km}"]
        kc_lower = dataframe[f"kc_lower_{kp}_{km}"]

        # Squeeze : BB est à l'intérieur du KC
        squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)

        # Squeeze release : squeeze était active dans les N dernières bougies
        # mais n'est plus active maintenant
        squeeze_was_active = squeeze.shift(1).fillna(False)
        for i in range(2, lookback + 1):
            squeeze_was_active = squeeze_was_active | squeeze.shift(i).fillna(False)
        squeeze_released = squeeze_was_active & (~squeeze)

        # Breakout haussier : close > BB upper
        breakout_up = dataframe["close"] > bb_upper

        # Momentum positif
        momentum_positive = dataframe["close"] > dataframe["close"].shift(mom_p)

        conditions = (
            squeeze_released
            & breakout_up
            & momentum_positive
            & (dataframe[vol_col] > self.volume_mult.value)
            & (dataframe[rsi_col] < self.rsi_max.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bp = self.bb_period.value
        bs = self.bb_std.value
        bb_middle = dataframe[f"bb_middle_{bp}_{bs}"]
        rsi_col = f"rsi_{self.rsi_period.value}"

        conditions = (
            (dataframe["close"] < bb_middle)
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
