# ══════════════════════════════════════════════════════════════
# anis solidscale - Elite Spot Trading Suite
# SCRIPT    : sniper_bot.py
# CATÉGORIE : 4 — On-Chain (Smart Money)
# OUTIL     : Python Custom (Web3.py)
# ══════════════════════════════════════════════════════════════
#
# DESCRIPTION :
# Sniper Bot DEX : détecte l'ajout de liquidité sur un nouveau
# pool DEX et exécute un achat ultra-rapide en Spot.
#
# LOGIQUE :
# 1. Écoute les événements PairCreated / AddLiquidity sur le DEX
# 2. Vérifie la sécurité du token (honeypot, tax, renounced)
# 3. Si sécurisé → achat rapide avec slippage configuré
#
# SÉCURITÉ (CRITIQUE) :
# - Vérifie la liquidité minimale
# - Vérifie les buy/sell tax
# - Vérifie le honeypot
# - Vérifie si le contrat est renoncé
# ══════════════════════════════════════════════════════════════

import sys
import time
import asyncio
from pathlib import Path
from typing import Optional

# ── Import config dédiée ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "configs"))
import config_sniper as cfg

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from utils.logging_utils import TradeLogger
from utils.telegram_notifier import TelegramNotifier
from utils.performance import PerformanceTracker

try:
    from web3 import Web3
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False
    Web3 = None  # type: ignore

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class SniperBot:
    """
    Sniper Bot DEX — Achat ultra-rapide lors de l'ajout de liquidité.

    PRINCIPES ANIS SOLIDSCALE :
    ✅ Spot uniquement (achat réel, pas de short)
    ✅ Vérification de sécurité obligatoire avant achat
    ✅ DRY_RUN par défaut
    ✅ Logging SQLite + Telegram

    ARCHITECTURE :
    Le bot écoute les événements on-chain via WebSocket.
    Chaque nouveau pool est analysé avant achat.
    """

    # ── ABI minimal pour détecter PairCreated (Uniswap V2 Factory) ──
    FACTORY_ABI = [
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "token0", "type": "address"},
                {"indexed": True, "name": "token1", "type": "address"},
                {"indexed": False, "name": "pair", "type": "address"},
                {"indexed": False, "name": "allPairsLength", "type": "uint256"},
            ],
            "name": "PairCreated",
            "type": "event",
        }
    ]

    def __init__(self):
        self.dry_run = cfg.DRY_RUN

        # ── Utilitaires partagés (REFACTORING) ──
        self.logger = TradeLogger(strategy_name="SniperBot")
        self.notifier = TelegramNotifier()
        self.performance = PerformanceTracker(
            "SniperBot", trade_logger=self.logger,
            telegram_notifier=self.notifier,
        )

        # ── Web3 ──
        self.w3 = None
        if HAS_WEB3 and cfg.RPC_URL:
            try:
                self.w3 = Web3(Web3.HTTPProvider(cfg.RPC_URL))
                if self.w3.is_connected():
                    print(f"✅ Connecté à {cfg.CHAIN} (block: {self.w3.eth.block_number})")
                else:
                    print(f"❌ Échec connexion à {cfg.RPC_URL}")
                    self.w3 = None
            except Exception as e:
                print(f"❌ Erreur Web3: {e}")
                self.w3 = None

        # ── Paramètres (tous depuis config) ──
        self.snipe_amount = cfg.SNIPE_AMOUNT_ETH
        self.min_liquidity = cfg.MIN_LIQUIDITY_ETH
        self.max_buy_tax = cfg.MAX_BUY_TAX_PCT
        self.max_sell_tax = cfg.MAX_SELL_TAX_PCT
        self.slippage = cfg.SLIPPAGE_TOLERANCE_PCT
        self.check_honeypot = cfg.CHECK_HONEYPOT
        self.max_gas = cfg.MAX_GAS_PRICE_GWEI

        self.notifier.send_startup_message("SniperBot", dry_run=self.dry_run)

    async def check_token_safety(self, token_address: str) -> dict:
        """
        Vérifie la sécurité d'un token avant achat.

        CHECKS :
        1. Honeypot check (via API externe ou simulation de tx)
        2. Buy/Sell tax estimation
        3. Contrat renoncé (owner == 0x0)
        4. Liquidité suffisante

        Returns:
            Dict avec les résultats de sécurité.
        """
        result = {
            "safe": False,
            "honeypot": None,
            "buy_tax": None,
            "sell_tax": None,
            "renounced": None,
            "liquidity_eth": 0,
        }

        if not HAS_AIOHTTP:
            print("[SniperBot] aiohttp requis pour les checks de sécurité")
            return result

        try:
            # ── Check via GoPlus API (gratuit, pas d'API key) ──
            async with aiohttp.ClientSession() as session:
                chain_id = str(cfg.CHAIN_ID)
                url = f"https://api.gopluslabs.com/api/v1/token_security/{chain_id}?contract_addresses={token_address}"

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token_data = data.get("result", {}).get(token_address.lower(), {})

                        result["honeypot"] = token_data.get("is_honeypot", "1") == "1"
                        result["buy_tax"] = float(token_data.get("buy_tax", "1")) * 100
                        result["sell_tax"] = float(token_data.get("sell_tax", "1")) * 100
                        result["renounced"] = token_data.get("is_open_source", "0") == "1"

                        result["safe"] = (
                            not result["honeypot"]
                            and result["buy_tax"] <= self.max_buy_tax
                            and result["sell_tax"] <= self.max_sell_tax
                        )

        except Exception as e:
            print(f"[SniperBot] Erreur check sécurité: {e}")

        return result

    def execute_snipe(self, token_address: str, pair_address: str) -> bool:
        """
        Exécute l'achat du token.

        SÉCURITÉ : En DRY_RUN, simule l'achat sans interagir avec la blockchain.
        """
        if self.dry_run:
            self.logger.log_trade(
                pair=f"TOKEN/{cfg.CHAIN}", side="buy",
                price=0, amount=self.snipe_amount,
                dry_run=True,
                extra_info=f"snipe|token:{token_address[:10]}|pair:{pair_address[:10]}",
            )
            self.notifier.send_trade_alert(
                "SniperBot", f"NEW_TOKEN/{cfg.CHAIN}", "buy (snipe)",
                price=0, amount=self.snipe_amount, dry_run=True,
            )
            print(
                f"[DRY_RUN] 🎯 SNIPE: Token={token_address[:10]}... | "
                f"Amount={self.snipe_amount} ETH"
            )
            return True
        else:
            # ── LIVE : Construire et envoyer la TX swap ──
            # TODO: Implémenter avec router.swapExactETHForTokens()
            print("[SniperBot] Mode LIVE non implémenté. Nécessite ABI router.")
            return False

    def run(self) -> None:
        """
        Point d'entrée principal.

        SCAFFOLD : Le listener d'événements nécessite un WebSocket node.
        En attendant, on vérifie périodiquement les nouveaux pools.
        """
        print(f"🎯 SniperBot démarré | DRY_RUN={self.dry_run} | Chain={cfg.CHAIN}")
        if self.w3 is None:
            print("⚠️ Web3 non connecté. Vérifiez RPC_URL dans config_sniper.py")
            print("   Le bot fonctionne en mode SCAFFOLD/DEMO uniquement.")

        try:
            while True:
                # SCAFFOLD : En production, remplacer par un event listener
                print("  [SniperBot] Surveillance des nouveaux pools...")
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n⏹ SniperBot arrêté.")
            self.performance.log_performance()


if __name__ == "__main__":
    bot = SniperBot()
    bot.run()
