# ══════════════════════════════════════════════════════════════
# CONFIG : Whale Tracker
# Clés API lues depuis le .env (voir .env.example)
# ══════════════════════════════════════════════════════════════
import os
try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))
except ImportError:
    pass

DRY_RUN = True

# ── Blockchain ──
CHAIN = "ethereum"
RPC_URL = os.environ.get("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY")
CHAIN_ID = 1

# ── DexScreener API ──
DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex"

# ── Wallets Smart Money à tracker ──
# Format: { "label": "wallet_address" }
TRACKED_WALLETS = {
    "whale_1": "0x0000000000000000000000000000000000000001",
    "whale_2": "0x0000000000000000000000000000000000000002",
    # Ajouter vos adresses Smart Money identifiées ici
}

# ── Filtres ──
MIN_TX_VALUE_USD = 10000      # Ignorer les petites transactions
MIN_TOKEN_LIQUIDITY_USD = 50000
COPY_TRADE_AMOUNT_USD = 100   # Montant à copier par trade
MAX_PORTFOLIO_PER_TOKEN_PCT = 10  # Max 10% du portfolio par token

# ── Timing ──
POLL_INTERVAL_SECONDS = 15
BLOCK_CONFIRMATIONS = 2

# ── Notifications ──
TELEGRAM_ENABLED = True
ALERT_ON_NEW_POSITION = True
ALERT_ON_EXIT = True
LOG_TO_SQLITE = True
