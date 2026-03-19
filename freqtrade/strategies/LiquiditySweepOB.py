# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : LiquiditySweepOB
# CATÉGORIE : Smart Money — Liquidity Sweep + Order Block
# ══════════════════════════════════════════════════════════════
#
# LOGIQUE :
# 1. Détection de Liquidity Sweep : le prix fait un faux breakout
#    sous un swing low récent (déclenche les stops) puis remonte
# 2. Order Block bullish : dernière bougie rouge avant un mouvement
#    haussier de >1% dans les 3 bougies suivantes
# 3. RSI < seuil d'entrée (pas de surachat)
# 4. Sortie : prix atteint le swing high OU RSI > seuil exit
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


class LiquiditySweepOB(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 100

    minimal_roi = {"0": 0.10, "360": 0.05, "720": 0.02}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ── Buy params ──
    swing_lookback = IntParameter(3, 10, default=5, space="buy")
    rsi_period = IntParameter(7, 21, default=14, space="buy")
    rsi_entry = IntParameter(40, 65, default=55, space="buy")
    ob_threshold = DecimalParameter(0.005, 0.03, default=0.01, space="buy")
    volume_period = IntParameter(10, 50, default=20, space="buy")

    # ── Sell params ──
    rsi_exit = IntParameter(65, 85, default=75, space="sell")

    _logger = None
    _notifier = None

    def _init_utils(self) -> None:
        if self._logger is None:
            self._logger = TradeLogger(strategy_name="LiquiditySweepOB")
            self._notifier = TelegramNotifier()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._init_utils()

        # Pre-calculer RSI pour TOUTES les valeurs possibles (hyperopt-safe)
        for rsi_p in range(self.rsi_period.low, self.rsi_period.high + 1):
            dataframe = CommonIndicators.add_rsi(dataframe, period=rsi_p)

        # Pre-calculer volume SMA pour TOUTES les valeurs possibles
        for vol_p in range(self.volume_period.low, self.volume_period.high + 1):
            dataframe = CommonIndicators.add_volume_sma(dataframe, period=vol_p)

        # Swing highs/lows pour TOUTES les valeurs de lookback
        for lookback in range(self.swing_lookback.low, self.swing_lookback.high + 1):
            sh_col = f"swing_high_{lookback}"
            sl_col = f"swing_low_{lookback}"
            dataframe[sh_col] = np.nan
            dataframe[sl_col] = np.nan

            for i in range(lookback, len(dataframe) - lookback):
                high_val = dataframe["high"].iloc[i]
                is_swing = True
                for j in range(1, lookback + 1):
                    if high_val <= dataframe["high"].iloc[i - j] or high_val <= dataframe["high"].iloc[i + j]:
                        is_swing = False
                        break
                if is_swing:
                    dataframe.iloc[i, dataframe.columns.get_loc(sh_col)] = high_val

                low_val = dataframe["low"].iloc[i]
                is_swing = True
                for j in range(1, lookback + 1):
                    if low_val >= dataframe["low"].iloc[i - j] or low_val >= dataframe["low"].iloc[i + j]:
                        is_swing = False
                        break
                if is_swing:
                    dataframe.iloc[i, dataframe.columns.get_loc(sl_col)] = low_val

            dataframe[f"recent_swing_high_{lookback}"] = dataframe[sh_col].ffill()
            dataframe[f"recent_swing_low_{lookback}"] = dataframe[sl_col].ffill()

        # Order Block bullish : bougie rouge (close < open) suivie d'une hausse > threshold
        # dans les 3 bougies suivantes
        # Pre-calculer pour toutes les valeurs de ob_threshold
        # On utilise la valeur max du threshold pour le calcul, le filtrage se fait dans entry
        dataframe["is_red_candle"] = (dataframe["close"] < dataframe["open"]).astype(int)

        # Hausse max dans les 3 bougies suivantes par rapport au close de la bougie courante
        dataframe["future_max_close"] = dataframe["close"].shift(-1).rolling(3).max()
        dataframe["future_return"] = (
            (dataframe["future_max_close"] - dataframe["close"]) / dataframe["close"]
        )

        # Marquer les Order Blocks (bougie rouge avec hausse future > threshold)
        # On forward-fill le prix de l'OB pour savoir si le prix actuel est dans/au-dessus
        dataframe["ob_price_high"] = np.nan
        dataframe["ob_price_low"] = np.nan

        # On pre-calcule pour le seuil minimum (toutes les valeurs >= min seront couvertes)
        min_threshold = 0.005
        ob_mask = (dataframe["is_red_candle"] == 1) & (dataframe["future_return"] > min_threshold)
        dataframe.loc[ob_mask, "ob_price_high"] = dataframe.loc[ob_mask, "open"]
        dataframe.loc[ob_mask, "ob_price_low"] = dataframe.loc[ob_mask, "close"]
        dataframe["ob_price_high"] = dataframe["ob_price_high"].ffill()
        dataframe["ob_price_low"] = dataframe["ob_price_low"].ffill()
        dataframe["ob_future_return"] = np.nan
        dataframe.loc[ob_mask, "ob_future_return"] = dataframe.loc[ob_mask, "future_return"]
        dataframe["ob_future_return"] = dataframe["ob_future_return"].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        sl_col = f"recent_swing_low_{self.swing_lookback.value}"
        sh_col = f"recent_swing_high_{self.swing_lookback.value}"

        # Liquidity sweep : low passe sous le swing low mais close reste au-dessus (faux breakout)
        sweep = (
            (dataframe["low"] < dataframe[sl_col])
            & (dataframe["close"] > dataframe[sl_col])
        )

        # Prix dans/au-dessus de l'Order Block + OB valide pour le threshold courant
        in_ob = (
            (dataframe["close"] >= dataframe["ob_price_low"])
            & (dataframe["ob_future_return"] >= self.ob_threshold.value)
        )

        conditions = (
            sweep
            & in_ob
            & (dataframe[rsi_col] < self.rsi_entry.value)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_col = f"rsi_{self.rsi_period.value}"
        sh_col = f"recent_swing_high_{self.swing_lookback.value}"

        conditions = (
            (dataframe["close"] >= dataframe[sh_col])
            | (dataframe[rsi_col] > self.rsi_exit.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe
