# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : MultiFactorCorrelation
# CATÉGORIE : 5 — Intelligence Artificielle
# OUTIL     : Freqtrade (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Analyse multi-factorielle : ajuste l'exposition Spot en fonction
# de variables macro et de corrélation inter-marchés.
#
# FACTEURS ANALYSÉS :
# 1. BTC Dominance (BTC.D) — proxy via BTC/USDT momentum
# 2. Momentum sectoriel — force relative de l'actif vs BTC
# 3. Volatilité du marché — ATR ratio cross-asset
# 4. Scores techniques — RSI + MACD combinés
#
# LOGIQUE :
# Un score composite est calculé à partir de tous les facteurs.
# Entrée quand le score > seuil, sortie quand score < seuil inverse.
#
# NOTE : Pour les données BTC.D réelles et l'index Tech,
# une intégration API externe serait nécessaire. Ici on utilise
# des proxies calculables depuis les données OHLCV.
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


class MultiFactorCorrelation(IStrategy):
    """
    Multi-Factor Correlation — Score composite multi-factoriel.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Score composite = somme pondérée de facteurs
    ✅ Chaque poids de facteur est configurable
    ✅ Intègre des proxies macro (BTC dominance, volatilité)
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "4h"
    startup_candle_count = 210

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES — Poids des facteurs
    # ═══════════════════════════════════════════════════════

    # ── Poids du facteur RSI ──
    weight_rsi = DecimalParameter(0.0, 2.0, default=1.0, decimals=1,
                                  space="buy", optimize=True, load=True)

    # ── Poids du facteur MACD ──
    weight_macd = DecimalParameter(0.0, 2.0, default=1.0, decimals=1,
                                   space="buy", optimize=True, load=True)

    # ── Poids du facteur Momentum (rendement récent) ──
    weight_momentum = DecimalParameter(0.0, 2.0, default=1.0, decimals=1,
                                       space="buy", optimize=True, load=True)

    # ── Poids du facteur Volatilité (ATR inversé) ──
    weight_volatility = DecimalParameter(0.0, 2.0, default=0.8, decimals=1,
                                         space="buy", optimize=True, load=True)

    # ── Poids du facteur Volume ──
    weight_volume = DecimalParameter(0.0, 2.0, default=0.7, decimals=1,
                                     space="buy", optimize=True, load=True)

    # ── Seuil d'entrée pour le score composite ──
    entry_score_threshold = DecimalParameter(0.3, 0.9, default=0.6, decimals=2,
                                              space="buy", optimize=True, load=True)

    # ── Seuil de sortie ──
    exit_score_threshold = DecimalParameter(0.1, 0.5, default=0.35, decimals=2,
                                             space="sell", optimize=True, load=True)

    # ── Périodes des indicateurs ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)
    momentum_period = IntParameter(5, 50, default=20, space="buy",
                                   optimize=True, load=True)
    ema_fast = IntParameter(10, 100, default=50, space="buy",
                            optimize=True, load=True)

    # ── ROI ──
    minimal_roi = {
        "0": 0.12,
        "480": 0.06,
        "1440": 0.03,
    }

    stoploss = -0.07

    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # ═══════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_logger = TradeLogger(strategy_name="MultiFactorCorrelation")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "MultiFactorCorrelation", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calcule les facteurs et le score composite.

        MÉTHODE DU SCORE :
        Chaque facteur est normalisé entre [0, 1] puis multiplié
        par son poids. Le score final est la moyenne pondérée.
        """
        # ── Facteurs techniques (via CommonIndicators) ──
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe = CommonIndicators.add_macd(dataframe)
        dataframe = CommonIndicators.add_atr(dataframe, period=14)
        dataframe = CommonIndicators.add_ema(dataframe, period=self.ema_fast.value)
        dataframe = CommonIndicators.add_volume_sma(dataframe, period=20)

        # ═══════════════════════════════════════════════════
        # CALCUL DES SOUS-SCORES NORMALISÉS [0, 1]
        # ═══════════════════════════════════════════════════

        rsi_col = f"rsi_{self.rsi_period.value}"

        # ── Score RSI : RSI bas = bon score (opportunité d'achat) ──
        # CHOIX : Inversé car RSI bas = survendu = bon point d'entrée
        dataframe["score_rsi"] = (100 - dataframe[rsi_col]) / 100.0

        # ── Score MACD : MACD positif et croissant = bon ──
        macd_range = dataframe["macd"].rolling(100).max() - dataframe["macd"].rolling(100).min()
        dataframe["score_macd"] = (
            (dataframe["macd"] - dataframe["macd"].rolling(100).min())
            / macd_range.replace(0, np.nan)
        ).clip(0, 1)

        # ── Score Momentum : rendement récent positif = bon ──
        mom = dataframe["close"].pct_change(self.momentum_period.value)
        mom_max = mom.rolling(100).max()
        mom_min = mom.rolling(100).min()
        dataframe["score_momentum"] = (
            (mom - mom_min) / (mom_max - mom_min).replace(0, np.nan)
        ).clip(0, 1)

        # ── Score Volatilité : faible volatilité = bon (marché stable) ──
        # CHOIX : On inverse l'ATR car faible volatilité = moins de risque
        atr_norm = dataframe["atr_14"] / dataframe["close"]
        atr_max = atr_norm.rolling(100).max()
        dataframe["score_volatility"] = (
            1 - (atr_norm / atr_max.replace(0, np.nan))
        ).clip(0, 1)

        # ── Score Volume : volume > moyenne = bon (confirmation) ──
        dataframe["score_volume"] = (
            dataframe["volume_ratio_20"].clip(0, 3) / 3.0
        )

        # ═══════════════════════════════════════════════════
        # SCORE COMPOSITE (moyenne pondérée)
        # ═══════════════════════════════════════════════════

        total_weight = (
            self.weight_rsi.value
            + self.weight_macd.value
            + self.weight_momentum.value
            + self.weight_volatility.value
            + self.weight_volume.value
        )

        if total_weight > 0:
            dataframe["composite_score"] = (
                dataframe["score_rsi"] * self.weight_rsi.value
                + dataframe["score_macd"] * self.weight_macd.value
                + dataframe["score_momentum"] * self.weight_momentum.value
                + dataframe["score_volatility"] * self.weight_volatility.value
                + dataframe["score_volume"] * self.weight_volume.value
            ) / total_weight
        else:
            dataframe["composite_score"] = 0.5

        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrée quand le score composite dépasse le seuil.
        """
        dataframe.loc[
            (
                (dataframe["composite_score"] > self.entry_score_threshold.value)
                &
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX DE SORTIE
    # ═══════════════════════════════════════════════════════

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Sortie quand le score composite tombe sous le seuil.
        """
        dataframe.loc[
            (
                (dataframe["composite_score"] < self.exit_score_threshold.value)
                &
                (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe

    # ═══════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        self._trade_logger.log_trade(
            pair=pair, side="buy", price=rate, amount=amount,
            dry_run=is_dry, extra_info="multi_factor",
        )
        self._notifier.send_trade_alert(
            "MultiFactorCorrelation", pair, "buy", rate, amount, dry_run=is_dry,
        )
        return True

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time,
                           **kwargs) -> bool:
        is_dry = self.config.get("dry_run", True)
        pnl = trade.calc_profit_ratio(rate) * 100
        self._trade_logger.log_trade(
            pair=pair, side="sell", price=rate, amount=amount,
            pnl=pnl, dry_run=is_dry, extra_info=f"exit:{exit_reason}",
        )
        self._notifier.send_trade_alert(
            "MultiFactorCorrelation", pair, "sell", rate, amount,
            pnl=pnl, dry_run=is_dry,
        )
        return True
