# ══════════════════════════════════════════════════════════════
# CONFIG : Index Rebalancer
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

# ── Exchange pour l'exécution ──
EXCHANGE = "bitget"
API_KEY = os.environ.get("BITGET_API_KEY", "")
API_SECRET = os.environ.get("BITGET_API_SECRET", "")
API_PASSWORD = os.environ.get("BITGET_API_PASSWORD", "")

# ── Composition de l'index ──
# Panier thématique avec poids cibles (doivent sommer à 100)
INDEX_COMPOSITION = {
    # ── Thème: Top Market Caps ──
    "BTC/USDT": 30,   # 30%
    "ETH/USDT": 25,   # 25%
    "SOL/USDT": 15,   # 15%
    "BNB/USDT": 10,   # 10%
    "XRP/USDT": 10,   # 10%
    "ADA/USDT": 5,    # 5%
    "AVAX/USDT": 5,   # 5%
}

# ── Paramètres de rééquilibrage ──
TOTAL_PORTFOLIO_USDT = 10000
REBALANCE_THRESHOLD_PCT = 3.0  # Rebalance si déviation > 3%
REBALANCE_INTERVAL_HOURS = 24  # Vérifier toutes les 24h
MIN_TRADE_USDT = 10            # Ignorer les rebalances < 10 USDT

# ── Frais ──
ESTIMATED_FEE_PCT = 0.1

# ── Notifications ──
TELEGRAM_ENABLED = True
SEND_DAILY_REPORT = True
LOG_TO_SQLITE = True
