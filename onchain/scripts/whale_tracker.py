# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : whale_tracker.py
# CATÉGORIE : 4 — On-Chain (Smart Money)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Réplication automatique des mouvements Spot des portefeuilles
# identifiés comme "Smart Money". Surveille les transactions
# on-chain et utilise DexScreener pour les données de prix.
#
# LOGIQUE :
# 1. Surveille les wallets configurés via RPC / DexScreener
# 2. Détecte les nouveaux achats/ventes importants
# 3. Réplique le trade avec un montant configurable
# ══════════════════════════════════════════════════════════════

import sys
import time
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "configs"))
import config_whale_tracker as cfg

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.performance import PerformanceTracker

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False


class WhaleTracker:
    """
    Whale Tracker — Suivi et réplication des Smart Money wallets.

    ARCHITECTURE :
    1. DexScreener API pour les données de marché (gratuit, rate-limited)
    2. Web3.py pour lire les transactions on-chain
    3. Détection des gros mouvements (> min_tx_value)
    4. Réplication avec risk management (max par token)
    """

    def __init__(self):
        self.dry_run = cfg.DRY_RUN

        self.logger = TradeLogger(strategy_name="WhaleTracker")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "WhaleTracker", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        # ── Web3 ──
        self.w3 = None
        if HAS_WEB3 and cfg.RPC_URL:
            try:
                self.w3 = Web3(Web3.HTTPProvider(cfg.RPC_URL))
                if self.w3.is_connected():
                    print(f"✅ Connecté à {cfg.CHAIN}")
            except Exception as e:
                print(f"❌ Erreur Web3: {e}")

        # ── Paramètres (depuis config) ──
        self.tracked_wallets = cfg.TRACKED_WALLETS
        self.min_tx_value = cfg.MIN_TX_VALUE_USD
        self.copy_amount = cfg.COPY_TRADE_AMOUNT_USD
        self.poll_interval = cfg.POLL_INTERVAL_SECONDS
        self.dexscreener_url = cfg.DEXSCREENER_API_URL

        # ── Cache des dernières TX connues par wallet ──
        self._last_tx_hash: dict[str, str] = {}

        self.notifier.send_startup_message("WhaleTracker", dry_run=self.dry_run)

    def get_token_info(self, token_address: str) -> Optional[dict]:
        """
        Récupère les infos d'un token via DexScreener API.

        CHOIX : DexScreener est gratuit, pas de clé API requise,
        et fournit des données temps réel sur les pools DEX.

        Returns:
            Dict avec prix, liquidité, volume, etc.
        """
        if not HAS_REQUESTS:
            return None

        try:
            url = f"{self.dexscreener_url}/tokens/{token_address}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Prendre la paire la plus liquide
                    best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))
                    return {
                        "symbol": best.get("baseToken", {}).get("symbol", "UNKNOWN"),
                        "price_usd": float(best.get("priceUsd", 0)),
                        "liquidity_usd": float(best.get("liquidity", {}).get("usd", 0)),
                        "volume_24h": float(best.get("volume", {}).get("h24", 0)),
                        "pair_address": best.get("pairAddress", ""),
                        "dex": best.get("dexId", ""),
                    }
            return None
        except Exception as e:
            print(f"[WhaleTracker] Erreur DexScreener: {e}")
            return None

    def check_wallet_activity(self, label: str, wallet_address: str) -> list[dict]:
        """
        Vérifie les transactions récentes d'un wallet.

        SCAFFOLD : En production, utiliser un service d'indexation
        (Etherscan API, Alchemy, Moralis) pour l'historique des TX.
        Ici on vérifie les derniers blocs via Web3.
        """
        activities = []

        if self.w3 is None:
            return activities

        try:
            # Vérifier les derniers blocs pour des transactions de ce wallet
            latest_block = self.w3.eth.block_number
            block = self.w3.eth.get_block(latest_block, full_transactions=True)

            for tx in block.get("transactions", []):
                if isinstance(tx, dict):
                    from_addr = tx.get("from", "").lower()
                    if from_addr == wallet_address.lower():
                        value_eth = self.w3.from_wei(tx.get("value", 0), "ether")
                        tx_hash = tx.get("hash", b"").hex()

                        # Éviter les doublons
                        if tx_hash == self._last_tx_hash.get(label):
                            continue

                        self._last_tx_hash[label] = tx_hash

                        activities.append({
                            "label": label,
                            "wallet": wallet_address,
                            "tx_hash": tx_hash,
                            "value_eth": float(value_eth),
                            "to": tx.get("to", ""),
                            "input": tx.get("input", "0x")[:10],  # Fonction selector
                        })

        except Exception as e:
            print(f"[WhaleTracker] Erreur scan {label}: {e}")

        return activities

    def copy_trade(self, activity: dict) -> bool:
        """
        Réplique un trade détecté d'un wallet Smart Money.
        """
        if self.dry_run:
            self.logger.log_trade(
                pair=f"COPY/{activity['label']}", side="buy",
                price=0, amount=self.copy_amount,
                dry_run=True,
                extra_info=json.dumps({
                    "whale": activity["label"],
                    "tx": activity["tx_hash"][:16],
                    "value_eth": activity["value_eth"],
                }),
            )
            self.notifier.send_trade_alert(
                "WhaleTracker", f"COPY/{activity['label']}", "copy_buy",
                price=0, amount=self.copy_amount, dry_run=True,
            )
            print(
                f"[DRY_RUN] 🐋 {activity['label']}: "
                f"TX valeur={activity['value_eth']:.4f} ETH | "
                f"→ Copy trade: {self.copy_amount} USD"
            )
            return True
        return False

    def run(self) -> None:
        """Boucle principale."""
        print(f"🐋 WhaleTracker démarré | DRY_RUN={self.dry_run}")
        print(f"   Wallets surveillés: {len(self.tracked_wallets)}")

        try:
            while True:
                for label, address in self.tracked_wallets.items():
                    activities = self.check_wallet_activity(label, address)
                    for activity in activities:
                        self.copy_trade(activity)
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\n⏹ WhaleTracker arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = WhaleTracker()
    bot.run()
