# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# MODULE : logging_utils.py
# RÔLE  : Logger centralisé CSV + SQLite pour TOUTES les stratégies
# ══════════════════════════════════════════════════════════════
#
# ARCHITECTURE DE REFACTORING :
# → Ce module est importé par TOUTES les stratégies (Freqtrade,
#   Hummingbot, OnChain). Aucune stratégie ne doit recréer ses
#   propres fonctions de logging.
#
# CHOIX TECHNIQUES :
# 1. SQLite est utilisé comme stockage principal car :
#    - Pas besoin de serveur externe
#    - Supporte les requêtes SQL pour l'analyse
#    - Une table PAR stratégie pour isolation des données
# 2. CSV est gardé comme export lisible (backup/audit)
# 3. Thread-safe grâce à threading.Lock (Freqtrade est multi-thread)
#
# USAGE :
#   from utils.logging_utils import TradeLogger
#   logger = TradeLogger(strategy_name="GridTradingSpot")
#   logger.log_trade(pair="BTC/USDT", side="buy", price=65000, ...)
# ══════════════════════════════════════════════════════════════

import csv
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class TradeLogger:
    """
    Logger centralisé pour enregistrer chaque trade dans SQLite + CSV.

    PRINCIPE ANIS SOLIDSCALE :
    - Chaque stratégie a sa propre table SQLite (isolation)
    - Les logs incluent : prix, frais, slippage, PnL simulé
    - Thread-safe pour utilisation avec Freqtrade
    - Auto-création des répertoires et fichiers
    """

    # ── Chemin par défaut de la base SQLite ──
    # Configurable via le constructeur. Par défaut : ft_userdata/logs/trades.db
    DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "logs"

    def __init__(
        self,
        strategy_name: str,
        db_dir: Optional[str] = None,
        csv_enabled: bool = True,
    ):
        """
        Initialise le logger pour une stratégie spécifique.

        Args:
            strategy_name: Nom de la stratégie (ex: "GridTradingSpot").
                           Utilisé comme nom de table SQLite et nom de fichier CSV.
            db_dir: Répertoire de la base SQLite. Si None, utilise DEFAULT_DB_DIR.
            csv_enabled: Si True, écrit aussi dans un fichier CSV (backup).
        """
        self.strategy_name = strategy_name
        # ── Normaliser le nom pour utilisation comme table SQL ──
        self._table_name = strategy_name.lower().replace(" ", "_").replace("-", "_")
        self.csv_enabled = csv_enabled
        self._lock = threading.Lock()

        # ── Créer le répertoire de logs ──
        self._db_dir = Path(db_dir) if db_dir else self.DEFAULT_DB_DIR
        self._db_dir.mkdir(parents=True, exist_ok=True)

        # ── Chemins des fichiers ──
        self._db_path = self._db_dir / "trades.db"
        self._csv_path = self._db_dir / f"trades_{self._table_name}.csv"

        # ── Initialiser la table SQLite ──
        self._init_db()

        # ── Initialiser le fichier CSV (si activé) ──
        if self.csv_enabled:
            self._init_csv()

    def _init_db(self) -> None:
        """
        Crée la table SQLite pour cette stratégie si elle n'existe pas.

        CHOIX : Une table par stratégie permet de :
        - Requêter les performances d'une stratégie indépendamment
        - Éviter les conflits entre stratégies concurrentes
        - Faciliter la purge ou l'export par stratégie
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    pair        TEXT    NOT NULL,
                    side        TEXT    NOT NULL,        -- 'buy' ou 'sell'
                    price       REAL    NOT NULL,
                    amount      REAL    NOT NULL,
                    fee         REAL    DEFAULT 0.0,     -- Frais en quote currency
                    fee_pct     REAL    DEFAULT 0.0,     -- Frais en pourcentage
                    slippage    REAL    DEFAULT 0.0,     -- Slippage estimé (%)
                    pnl         REAL    DEFAULT 0.0,     -- PnL simulé (DRY_RUN)
                    pnl_pct     REAL    DEFAULT 0.0,     -- PnL en pourcentage
                    balance     REAL    DEFAULT 0.0,     -- Solde après trade
                    dry_run     INTEGER DEFAULT 1,       -- 1 = paper, 0 = live
                    extra_info  TEXT    DEFAULT '',       -- JSON libre (infos custom)
                    created_at  TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    def _init_csv(self) -> None:
        """Crée le fichier CSV avec les headers si il n'existe pas."""
        if not self._csv_path.exists():
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "pair", "side", "price", "amount",
                    "fee", "fee_pct", "slippage", "pnl", "pnl_pct",
                    "balance", "dry_run", "extra_info",
                ])

    def log_trade(
        self,
        pair: str,
        side: str,
        price: float,
        amount: float,
        fee: float = 0.0,
        fee_pct: float = 0.0,
        slippage: float = 0.0,
        pnl: float = 0.0,
        pnl_pct: float = 0.0,
        balance: float = 0.0,
        dry_run: bool = True,
        extra_info: str = "",
    ) -> None:
        """
        Enregistre un trade dans SQLite + CSV (thread-safe).

        IMPORTANT : Cette méthode est la SEULE façon d'enregistrer un trade.
        Toutes les stratégies doivent l'utiliser au lieu de créer leur propre
        système de logging.

        Args:
            pair: Paire tradée (ex: "BTC/USDT")
            side: "buy" ou "sell"
            price: Prix d'exécution
            amount: Quantité tradée
            fee: Frais absolus en quote currency
            fee_pct: Frais en pourcentage
            slippage: Slippage estimé en pourcentage
            pnl: Profit/Perte simulé (pertinent en DRY_RUN)
            pnl_pct: PnL en pourcentage
            balance: Solde après ce trade
            dry_run: True si paper trading, False si live
            extra_info: Informations supplémentaires (JSON string)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # ── SQLite ──
            try:
                with sqlite3.connect(str(self._db_path)) as conn:
                    conn.execute(
                        f"""INSERT INTO {self._table_name}
                        (timestamp, pair, side, price, amount, fee, fee_pct,
                         slippage, pnl, pnl_pct, balance, dry_run, extra_info)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            timestamp, pair, side, price, amount, fee, fee_pct,
                            slippage, pnl, pnl_pct, balance, int(dry_run),
                            extra_info,
                        ),
                    )
                    conn.commit()
            except sqlite3.Error as e:
                # Ne pas crasher la stratégie si le logging échoue
                print(f"[TradeLogger:{self.strategy_name}] Erreur SQLite: {e}")

            # ── CSV (backup) ──
            if self.csv_enabled:
                try:
                    with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp, pair, side, price, amount, fee, fee_pct,
                            slippage, pnl, pnl_pct, balance, int(dry_run),
                            extra_info,
                        ])
                except OSError as e:
                    print(f"[TradeLogger:{self.strategy_name}] Erreur CSV: {e}")

    def get_trades(self, limit: int = 100) -> list[dict]:
        """
        Récupère les N derniers trades de cette stratégie depuis SQLite.

        Utilisé par PerformanceTracker pour calculer les métriques.
        """
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT * FROM {self._table_name} ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_trades(self) -> list[dict]:
        """Récupère tous les trades (attention : peut être volumineux)."""
        return self.get_trades(limit=999_999)

    def get_trade_count(self) -> int:
        """Retourne le nombre total de trades enregistrés."""
        with sqlite3.connect(str(self._db_path)) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {self._table_name}"
            )
            return cursor.fetchone()[0]
