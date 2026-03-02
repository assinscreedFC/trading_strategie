# ══════════════════════════════════════════════════════════════
# CONFIG : Sniper Bot (DEX Launch)
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
CHAIN = "ethereum"  # ethereum, bsc, polygon, arbitrum, base
RPC_URL = os.environ.get("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY")
CHAIN_ID = 1
WEBSOCKET_URL = os.environ.get("ETH_WS_URL", "wss://eth-mainnet.g.alchemy.com/v2/YOUR_KEY")

# ── Wallet (lus depuis .env — JAMAIS en clair) ──
PRIVATE_KEY = os.environ.get("ETH_PRIVATE_KEY", "")
WALLET_ADDRESS = os.environ.get("ETH_WALLET_ADDRESS", "")

# ── Router Uniswap V2/V3 ──
ROUTER_ADDRESS = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"  # Uniswap V2

# ── Paramètres du snipe ──
SNIPE_AMOUNT_ETH = 0.1
MIN_LIQUIDITY_ETH = 5.0      # Min liquidité dans le pool pour sniper
MAX_BUY_TAX_PCT = 10.0       # Rejeter si buy tax > 10%
MAX_SELL_TAX_PCT = 10.0       # Rejeter si sell tax > 10%
SLIPPAGE_TOLERANCE_PCT = 15.0 # Slippage max toléré

# ── Sécurité ──
CHECK_HONEYPOT = True         # Vérifier si le token est un honeypot
CHECK_RENOUNCED = True        # Vérifier si le contrat est renoncé
MAX_GAS_PRICE_GWEI = 100
GAS_LIMIT = 300000

# ── Timing ──
LISTEN_PENDING_TX = True      # Écouter les TX pending pour vitesse
RETRY_COUNT = 3

# ── Notifications ──
TELEGRAM_ENABLED = True
LOG_TO_SQLITE = True
