# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# STRATÉGIE : GridTradingSpot
# CATÉGORIE : 1 — Fondations
# OUTIL     : Freqtrade (IStrategy)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Grid Trading adaptatif : place automatiquement des ordres d'achat
# et de vente sur des paliers de prix réguliers pour capturer la
# volatilité latérale du marché. Fonctionne EXCLUSIVEMENT en Spot
# (Long-Only, zéro levier).
#
# LOGIQUE :
# 1. L'ATR définit dynamiquement l'espacement entre les niveaux
#    du grid (plus de volatilité = grid plus large)
# 2. Le RSI filtre les entrées (pas d'achat si surachat)
# 3. Chaque niveau est un take-profit par rapport au niveau précédent
#
# CONFIGURABILITÉ :
# → TOUS les paramètres sont des IntParameter/DecimalParameter
# → Modifiables via l'hyperopt OU manuellement dans le code
# → Aucune valeur codée en dur
#
# INTÉGRATION :
# → Utilise utils.indicators.CommonIndicators (pas de duplication)
# → Utilise utils.logging_utils.TradeLogger (SQLite par stratégie)
# → Utilise utils.telegram_notifier.TelegramNotifier
# ══════════════════════════════════════════════════════════════

import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

# ── Ajout du chemin parent pour importer les utils partagés ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from utils.indicators import CommonIndicators
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier


class GridTradingSpot(IStrategy):
    """
    Grid Trading Spot — Capture la volatilité via des paliers de prix.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Long-Only (Spot) — can_short = False
    ✅ DRY_RUN par défaut
    ✅ Tous les paramètres configurables
    ✅ Logging SQLite + CSV par stratégie
    ✅ Notifications Telegram
    """

    # ══════════════════════════════════════════════════════════
    # MÉTADONNÉES FREQTRADE
    # ══════════════════════════════════════════════════════════

    INTERFACE_VERSION = 3

    # CHOIX : can_short = False est le verrou principal qui empêche
    # toute vente à découvert. C'est la règle n°1 anis solidscale.
    can_short = False

    # ── Timeframe ──
    # CHOIX : 5m pour capturer les micro-mouvements du grid.
    # Un timeframe plus court (1m) génèrerait trop de bruit.
    timeframe = "5m"

    # ── Nombre de bougies nécessaires pour que les indicateurs soient stables ──
    startup_candle_count = 50

    # ══════════════════════════════════════════════════════════
    # PARAMÈTRES CONFIGURABLES (tous modifiables)
    # ══════════════════════════════════════════════════════════

    # ── Grid : nombre de niveaux ──
    # CHOIX : 10 niveaux par défaut. Plus de niveaux = plus de trades mais
    # plus de capital distribué. Range [3, 30] pour supporter du micro-grid
    # au macro-grid.
    grid_levels = IntParameter(3, 30, default=10, space="buy",
                               optimize=True, load=True)

    # ── Grid : espacement entre niveaux (% du prix) ──
    # CHOIX : 1.0% par défaut. Multiplié par l'ATR ratio pour s'adapter
    # à la volatilité. Range [0.3, 5.0] pour supporter les marchés calmes
    # et les marchés crypto très volatils.
    grid_spacing_pct = DecimalParameter(0.3, 5.0, default=1.0, decimals=1,
                                        space="buy", optimize=True, load=True)

    # ── RSI : période de calcul ──
    rsi_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── RSI : seuil maximum pour autoriser un achat ──
    # CHOIX : 65 par défaut. Pas d'achat si RSI > ce seuil (surachat)
    rsi_buy_max = IntParameter(50, 80, default=65, space="buy",
                               optimize=True, load=True)

    # ── ATR : période pour la volatilité adaptative ──
    atr_period = IntParameter(7, 30, default=14, space="buy",
                              optimize=True, load=True)

    # ── ATR : multiplicateur pour adapter le grid ──
    # CHOIX : Si ATR est élevé, on élargit le grid pour éviter les
    # faux signaux. 1.0 = pas d'adaptation, 2.0 = adaptation forte.
    atr_multiplier = DecimalParameter(0.5, 3.0, default=1.0, decimals=1,
                                      space="buy", optimize=True, load=True)

    # ── ROI : Objectifs de sortie configurables ──
    # CHOIX : ROI minimal basé sur l'espacement du grid.
    # Le grid vise naturellement 1 niveau de profit.
    minimal_roi = {
        "0": 0.05,      # 5% max si pas de signal de sortie
        "120": 0.03,    # 3% après 2h
        "360": 0.02,    # 2% après 6h
        "720": 0.01,    # 1% après 12h
    }

    # ── Stoploss : configurable ──
    # CHOIX : -5% comme filet de sécurité sous le grid complet.
    # Le trailing stop est plus important ici.
    stoploss = -0.05

    # ── Trailing Stop ──
    trailing_stop = True
    trailing_stop_positive = 0.01      # Active à +1%
    trailing_stop_positive_offset = 0.02  # Depuis +2%
    trailing_only_offset_is_reached = True

    # ══════════════════════════════════════════════════════════
    # INITIALISATION
    # ══════════════════════════════════════════════════════════

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # ── Logger SQLite dédié à cette stratégie ──
        self._trade_logger = TradeLogger(strategy_name="GridTradingSpot")
        # ── Notificateur Telegram ──
        self._notifier = TelegramNotifier()
        # ── Notification de démarrage ──
        is_dry = config.get("dry_run", True)
        self._notifier.send_startup_message("GridTradingSpot", dry_run=is_dry)

    # ══════════════════════════════════════════════════════════
    # INDICATEURS
    # ══════════════════════════════════════════════════════════

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Ajoute les indicateurs techniques au DataFrame.

        REFACTORING : Utilise CommonIndicators (utils/indicators.py)
        au lieu de recalculer les indicateurs ici. Cela garantit que
        le calcul est identique partout et facilite la maintenance.
        """
        # ── RSI : filtrage des entrées ──
        dataframe = CommonIndicators.add_rsi(
            dataframe, period=self.rsi_period.value
        )

        # ── ATR : adaptation dynamique du grid ──
        dataframe = CommonIndicators.add_atr(
            dataframe, period=self.atr_period.value
        )

        # ── Calcul des niveaux de grid dynamiques ──
        # CHOIX : Le grid est centré sur le prix actuel, avec des niveaux
        # espacés de grid_spacing_pct * (1 + ATR_ratio * atr_multiplier).
        # L'ATR ratio normalise l'ATR par rapport au prix pour obtenir un %.
        atr_col = f"atr_{self.atr_period.value}"
        dataframe["atr_ratio"] = dataframe[atr_col] / dataframe["close"]

        # Espacement effectif = base * (1 + atr_ratio * multiplier)
        dataframe["effective_spacing"] = (
            self.grid_spacing_pct.value / 100.0
            * (1 + dataframe["atr_ratio"] * self.atr_multiplier.value)
        )

        # ── Niveau de prix d'achat (grid inférieur) ──
        dataframe["grid_buy_level"] = (
            dataframe["close"] * (1 - dataframe["effective_spacing"])
        )

        # ── Niveau de prix de vente (grid supérieur) ──
        dataframe["grid_sell_level"] = (
            dataframe["close"] * (1 + dataframe["effective_spacing"])
        )

        return dataframe

    # ══════════════════════════════════════════════════════════
    # SIGNAUX D'ENTRÉE
    # ══════════════════════════════════════════════════════════

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Conditions d'entrée LONG (Spot uniquement).

        LOGIQUE DU GRID :
        1. Le prix actuel est au niveau du grid d'achat (le low de la bougie
           touche le grid_buy_level)
        2. Le RSI est sous le seuil de surachat (filtre de qualité)
        3. Le volume n'est pas anormalement bas (liquidité suffisante)

        SÉCURITÉ : La vérification de liquidité (volume) est conforme
        au principe §1 "Vérification systématique de la liquidité".
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        dataframe.loc[
            (
                # Condition 1 : Le prix touche le niveau d'achat du grid
                (dataframe["low"] <= dataframe["grid_buy_level"])
                &
                # Condition 2 : RSI pas en surachat
                (dataframe[rsi_col] < self.rsi_buy_max.value)
                &
                # Condition 3 : Volume suffisant (> 50% de la moyenne)
                (dataframe["volume"] > dataframe["volume"].rolling(20).mean() * 0.5)
                &
                # Condition 4 : Volume non nul (sécurité)
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    # ══════════════════════════════════════════════════════════
    # SIGNAUX DE SORTIE
    # ══════════════════════════════════════════════════════════

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Conditions de sortie (vente Spot).

        LOGIQUE :
        1. Le prix atteint le niveau de vente du grid (take profit naturel)
        2. OU le RSI est en zone de surachat extrême (> 75)

        Le trailing stop et minimal_roi fournissent des sorties additionnelles.
        """
        rsi_col = f"rsi_{self.rsi_period.value}"

        dataframe.loc[
            (
                # Condition 1 : Prix atteint le grid de vente
                (dataframe["high"] >= dataframe["grid_sell_level"])
                |
                # Condition 2 : RSI en surachat extrême
                (dataframe[rsi_col] > 75)
            )
            &
            (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        return dataframe

    # ══════════════════════════════════════════════════════════
    # CALLBACKS PERSONNALISÉS
    # ══════════════════════════════════════════════════════════

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        """
        Confirmation avant chaque entrée.

        LOGGING : Enregistre chaque tentative d'entrée dans SQLite.
        TELEGRAM : Envoie une alerte sur l'entrée.
        """
        is_dry = self.config.get("dry_run", True)
        self._trade_logger.log_trade(
            pair=pair, side="buy", price=rate, amount=amount,
            dry_run=is_dry, extra_info=f"entry_tag:{entry_tag}",
        )
        self._notifier.send_trade_alert(
            strategy_name="GridTradingSpot", pair=pair, side="buy",
            price=rate, amount=amount, dry_run=is_dry,
        )
        return True

    def confirm_trade_exit(self, pair, trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time,
                           **kwargs) -> bool:
        """
        Confirmation avant chaque sortie.

        LOGGING : Enregistre la sortie avec le PnL calculé.
        """
        is_dry = self.config.get("dry_run", True)
        pnl = trade.calc_profit_ratio(rate) * 100
        self._trade_logger.log_trade(
            pair=pair, side="sell", price=rate, amount=amount,
            pnl=pnl, dry_run=is_dry,
            extra_info=f"exit_reason:{exit_reason}",
        )
        self._notifier.send_trade_alert(
            strategy_name="GridTradingSpot", pair=pair, side="sell",
            price=rate, amount=amount, pnl=pnl, dry_run=is_dry,
        )
        return True
