# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : LSTMEntryOptimizer
# CATÉGORIE : 5 — Intelligence Artificielle
# OUTIL     : Freqtrade + FreqAI (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Utilise un réseau LSTM (Long Short-Term Memory) pour identifier
# des patterns non-linéaires dans les séquences de prix et optimiser
# les points d'entrée Spot à haute probabilité.
#
# ARCHITECTURE :
# 1. Les séquences OHLCV sont normalisées et passées au modèle
# 2. Le LSTM produit un "score d'entrée" (probabilité de hausse)
# 3. L'entrée est déclenchée quand le score > seuil configurable
#
# PRÉ-REQUIS :
# → FreqAI avec PyTorch dans la config
# → freqai.model_training_parameters doit pointer vers un modèle LSTM
# → pip install torch torchvision
#
# NOTE :
# Cette stratégie est un SCAFFOLD qui définit la structure.
# Le modèle LSTM réel est entraîné par FreqAI automatiquement.
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


class LSTMEntryOptimizer(IStrategy):
    """
    LSTM Entry Optimizer — Patterns non-linéaires pour entrées Spot.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot)
    ✅ Séquences OHLCV normalisées comme features
    ✅ Seuils de score configurables
    ✅ Scaffold prêt pour FreqAI LSTM/PyTorch
    """

    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 150

    # ═══════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES
    # ═══════════════════════════════════════════════════════

    # ── Longueur de la séquence LSTM (lookback) ──
    # CHOIX : 48 bougies (48h en 1h) pour capturer 2 jours de patterns.
    # Le LSTM a besoin de séquences assez longues pour apprendre.
    sequence_length = IntParameter(12, 96, default=48, space="buy",
                                   optimize=True, load=True)

    # ── Seuil d'entrée (score de probabilité) ──
    # CHOIX : 0.6 = le modèle doit être confiant à 60%+ pour entrer.
    # Trop bas = beaucoup de faux signaux. Trop haut = peu de trades.
    entry_score_threshold = DecimalParameter(0.3, 0.9, default=0.6, decimals=1,
                                              space="buy", optimize=True, load=True)

    # ── Seuil de sortie ──
    exit_score_threshold = DecimalParameter(0.1, 0.5, default=0.3, decimals=1,
                                             space="sell", optimize=True, load=True)

    # ── RSI comme filtre supplémentaire ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    rsi_max_entry = IntParameter(50, 80, default=70, space="buy",
                                 optimize=True, load=True)

    # ── ROI ──
    minimal_roi = {
        "0": 0.12,
        "360": 0.06,
        "720": 0.03,
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
        self._trade_logger = TradeLogger(strategy_name="LSTMEntryOptimizer")
        self._notifier = TelegramNotifier()
        self._notifier.send_startup_message(
            "LSTMEntryOptimizer", dry_run=config.get("dry_run", True)
        )

    # ═══════════════════════════════════════════════════════
    # FEATURE ENGINEERING — FreqAI LSTM
    # ═══════════════════════════════════════════════════════

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs,
    ) -> DataFrame:
        """
        Features séquentielles pour le LSTM.

        CHOIX DES FEATURES :
        Les LSTM fonctionnent mieux avec des features normalisées.
        On utilise des rendements (log returns) plutôt que des prix bruts
        pour stationnariser les données.
        """
        # ── Rendements log normalisés ──
        dataframe["%-log_return"] = np.log(
            dataframe["close"] / dataframe["close"].shift(1)
        )

        # ── Range normalisé (volatilité intra-bougie) ──
        dataframe["%-hl_ratio"] = (
            (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        )

        # ── Volume normalisé (Z-score) ──
        vol_mean = dataframe["volume"].rolling(20).mean()
        vol_std = dataframe["volume"].rolling(20).std()
        dataframe["%-volume_zscore"] = (
            (dataframe["volume"] - vol_mean) / vol_std.replace(0, np.nan)
        )

        # ── Open-Close direction ──
        dataframe["%-oc_direction"] = np.where(
            dataframe["close"] > dataframe["open"], 1, -1
        )

        # ── RSI normalisé [0, 1] ──
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        dataframe["%-rsi_normalized"] = (
            dataframe[f"rsi_{self.rsi_period.value}"] / 100.0
        )

        # ── ATR normalisé ──
        dataframe = CommonIndicators.add_atr(dataframe, period=14)
        dataframe["%-atr_normalized"] = dataframe["atr_14"] / dataframe["close"]

        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Target pour le LSTM : classification binaire (monte/descend).

        CHOIX : Plutôt qu'une régression (% exact), on utilise une
        classification (1 = hausse > 1%, 0 = sinon). Les LSTM
        sont souvent meilleurs en classification pour le trading.
        """
        # Hausse de plus de 1% dans les 6 prochaines bougies
        future_return = (
            dataframe["close"].shift(-6) / dataframe["close"] - 1
        ) * 100

        dataframe["&-s_up_probability"] = np.where(
            future_return > 1.0, 1, 0
        ).astype(float)

        return dataframe

    # ═══════════════════════════════════════════════════════
    # INDICATEURS
    # ═══════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = CommonIndicators.add_rsi(dataframe, period=self.rsi_period.value)
        return dataframe

    # ═══════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ═══════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entrée quand le LSTM prédit une hausse avec confiance suffisante.
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        if "&-s_up_probability" in dataframe.columns:
            dataframe.loc[
                (
                    (dataframe["&-s_up_probability"] > self.entry_score_threshold.value)
                    &
                    (dataframe[rsi_col] < self.rsi_max_entry.value)
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
        if "&-s_up_probability" in dataframe.columns:
            dataframe.loc[
                (
                    (dataframe["&-s_up_probability"] < self.exit_score_threshold.value)
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
            dry_run=is_dry, extra_info="lstm_prediction",
        )
        self._notifier.send_trade_alert(
            "LSTMEntryOptimizer", pair, "buy", rate, amount, dry_run=is_dry,
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
            "LSTMEntryOptimizer", pair, "sell", rate, amount, pnl=pnl, dry_run=is_dry,
        )
        return True
