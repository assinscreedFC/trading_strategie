# ══════════════════════════════════════════════════════════════
# anis solidscale — Elite Spot Trading Suite
# FICHIER : env_loader.py
# RÔLE   : Charge le .env et expose les clés API de manière centralisée
# ══════════════════════════════════════════════════════════════
#
# USAGE :
#   from utils.env_loader import env
#   api_key = env.BINANCE_API_KEY
#
# CHOIX TECHNIQUE :
# python-dotenv charge le fichier .env au premier import.
# Toutes les clés sont accessibles via l'objet `env` (NamedTuple-like).
# Si une clé n'est pas définie, retourne "" (chaîne vide) sans crasher.
# ══════════════════════════════════════════════════════════════

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    # Fallback si python-dotenv n'est pas installé :
    # on charge juste les variables d'environnement système
    load_dotenv = None  # type: ignore


# ── Charger le fichier .env ──
# CHOIX : On cherche le .env à la racine du projet (ft_userdata/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if load_dotenv is not None and _env_path.exists():
    load_dotenv(str(_env_path), override=False)
    print(f"[env_loader] ✅ .env chargé depuis {_env_path}")
elif not _env_path.exists():
    print(
        f"[env_loader] ⚠️ Fichier .env non trouvé à {_env_path}. "
        "Copiez .env.example → .env et remplissez vos clés."
    )


class _EnvConfig:
    """
    Accesseur centralisé pour toutes les variables d'environnement.

    AVANTAGE : Un seul endroit pour lister et documenter toutes les
    variables utilisées dans le projet. Si une variable manque,
    retourne "" au lieu de crasher.
    """

    # ═══════════════════════════════════════════════════════
    # TELEGRAM
    # ═══════════════════════════════════════════════════════

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def TELEGRAM_CHAT_ID(self) -> str:
        return os.environ.get("TELEGRAM_CHAT_ID", "")

    # ═══════════════════════════════════════════════════════
    # BINANCE (exchange principal)
    # ═══════════════════════════════════════════════════════

    @property
    def BINANCE_API_KEY(self) -> str:
        return os.environ.get("BINANCE_API_KEY", "")

    @property
    def BINANCE_API_SECRET(self) -> str:
        return os.environ.get("BINANCE_API_SECRET", "")

    # ═══════════════════════════════════════════════════════
    # KRAKEN (régulé EU / PSAN France)
    # ═══════════════════════════════════════════════════════

    @property
    def KRAKEN_API_KEY(self) -> str:
        return os.environ.get("KRAKEN_API_KEY", "")

    @property
    def KRAKEN_API_SECRET(self) -> str:
        return os.environ.get("KRAKEN_API_SECRET", "")

    # ═══════════════════════════════════════════════════════
    # BLOCKCHAIN / ON-CHAIN
    # ═══════════════════════════════════════════════════════

    @property
    def ETH_RPC_URL(self) -> str:
        return os.environ.get("ETH_RPC_URL", "")

    @property
    def ETH_WS_URL(self) -> str:
        return os.environ.get("ETH_WS_URL", "")

    @property
    def ETH_PRIVATE_KEY(self) -> str:
        return os.environ.get("ETH_PRIVATE_KEY", "")

    @property
    def ETH_WALLET_ADDRESS(self) -> str:
        return os.environ.get("ETH_WALLET_ADDRESS", "")

    # ═══════════════════════════════════════════════════════
    # DEXSCREENER
    # ═══════════════════════════════════════════════════════

    @property
    def DEXSCREENER_API_URL(self) -> str:
        return os.environ.get(
            "DEXSCREENER_API_URL",
            "https://api.dexscreener.com/latest/dex",
        )

    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════

    def get_binance_config(self) -> dict:
        """Retourne la config CCXT pour Binance."""
        return {
            "apiKey": self.BINANCE_API_KEY,
            "secret": self.BINANCE_API_SECRET,
        }

    def get_kraken_config(self) -> dict:
        """Retourne la config CCXT pour Kraken."""
        return {
            "apiKey": self.KRAKEN_API_KEY,
            "secret": self.KRAKEN_API_SECRET,
        }

    def is_telegram_configured(self) -> bool:
        """Vérifie si Telegram est configuré."""
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)

    def is_blockchain_configured(self) -> bool:
        """Vérifie si les paramètres blockchain sont configurés."""
        return bool(self.ETH_RPC_URL and self.ETH_PRIVATE_KEY)


# ── Instance singleton exportée ──
env = _EnvConfig()
