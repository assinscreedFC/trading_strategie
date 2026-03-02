# 🏗️ anis solidscale — Elite Spot Trading Suite

> Comprehensive crypto spot trading suite across **Freqtrade**, **Hummingbot**, and **custom on-chain** scripts.

## ⚠️ Important

- **ALL strategies default to `DRY_RUN = true`** — no real trades without explicit activation
- **Spot-only** — zero leverage, zero short selling, `can_short = False` enforced
- API keys are **blank placeholders** — fill them in before live trading

---

## 📁 Project Structure

```
ft_userdata/
├── freqtrade/                    # Freqtrade strategies (Cat. 1 & 5)
│   ├── config_bitget.json        # Bitget exchange config
│   ├── config_mexc.json          # MEXC exchange config (lowest fees)
│   ├── strategies/
│   │   ├── GridTradingSpot.py    # ATR-adaptive grid trading
│   │   ├── DCADynamique.py       # RSI-weighted dollar cost averaging
│   │   ├── TrendFollowing.py     # Golden Cross + Breakout
│   │   ├── MeanReversion.py      # Bollinger Bands bounce
│   │   ├── FreqAIXGBoost.py      # XGBoost ML predictions (FreqAI)
│   │   ├── LSTMEntryOptimizer.py # LSTM neural network (FreqAI)
│   │   └── MultiFactorCorrelation.py  # Weighted composite score
│   └── tests/
│       └── test_all_strategies.py
├── hummingbot/                   # Hummingbot scripts (Cat. 2 & 3)
│   ├── configs/                  # Per-strategy YAML configs
│   │   ├── config_arbitrage_spatial.yml
│   │   ├── config_arbitrage_triangulaire.yml
│   │   ├── config_relative_value.yml
│   │   ├── config_market_making.yml
│   │   ├── config_vwap_twap.yml
│   │   └── config_order_flow.yml
│   ├── scripts/
│   │   ├── arbitrage_spatial.py
│   │   ├── arbitrage_triangulaire.py
│   │   ├── relative_value_rotation.py
│   │   ├── market_making_dex.py
│   │   ├── vwap_twap_execution.py
│   │   └── order_flow_tracker.py
│   └── tests/
│       └── test_all_hummingbot.py
├── onchain/                      # On-chain scripts (Cat. 4)
│   ├── configs/
│   │   ├── config_sniper.py
│   │   ├── config_whale_tracker.py
│   │   └── config_index_rebalancer.py
│   ├── scripts/
│   │   ├── sniper_bot.py
│   │   ├── whale_tracker.py
│   │   └── index_rebalancer.py
│   └── tests/
│       └── test_all_onchain.py
├── utils/                        # Shared utilities (zero duplication)
│   ├── __init__.py
│   ├── env_loader.py             # 🔑 Centralised .env reader
│   ├── logging_utils.py          # SQLite + CSV per-strategy logging
│   ├── telegram_notifier.py      # Rate-limited Telegram alerts
│   ├── performance.py            # Metrics + weekly reports
│   └── indicators.py             # RSI, EMA, BB, ATR, ADX, MACD
├── .env                          # 🔑 VOS CLÉS API (ne pas committer)
├── .env.example                  # Template à copier vers .env
├── .gitignore
└── requirements.txt
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# → Ouvrir .env et remplir vos clés API

# 3. Run tests
python -m pytest freqtrade/tests/ hummingbot/tests/ onchain/tests/ -v

# 4. Run a Freqtrade strategy (dry-run)
freqtrade trade --strategy GridTradingSpot -c freqtrade/config_bitget.json

# 5. Run a Hummingbot script
python hummingbot/scripts/arbitrage_spatial.py

# 6. Run an on-chain script
python onchain/scripts/index_rebalancer.py
```

---

## 📊 Strategy Overview

| # | Strategy | Module | Description |
|---|----------|--------|-------------|
| 1 | GridTradingSpot | Freqtrade | ATR-adaptive grid, RSI filter |
| 2 | DCADynamique | Freqtrade | RSI-weighted DCA via `adjust_trade_position` |
| 3 | TrendFollowing | Freqtrade | Golden Cross / Breakout (configurable mode) |
| 4 | MeanReversion | Freqtrade | Bollinger Bands + RSI + Volume spike |
| 5 | FreqAIXGBoost | Freqtrade | ML price prediction (requires FreqAI) |
| 6 | LSTMEntryOptimizer | Freqtrade | Neural network entry scoring (requires FreqAI) |
| 7 | MultiFactorCorrelation | Freqtrade | Weighted composite from 5 factors |
| 8 | ArbitrageSpatial | Hummingbot | Cross-exchange spread capture |
| 9 | ArbitrageTriangulaire | Hummingbot | Single-exchange triangle cycle |
| 10 | RelativeValueRotation | Hummingbot | Z-score sector pairs trading |
| 11 | MarketMakingDEX | Hummingbot | Uniswap V3 LP (scaffold) |
| 12 | VWAPTWAPExecution | Hummingbot | Order slicing with randomization |
| 13 | OrderFlowTracker | Hummingbot | Orderbook wall detection & front-run |
| 14 | SniperBot | OnChain | DEX new pool sniper + safety checks |
| 15 | WhaleTracker | OnChain | Smart Money copy trading |
| 16 | IndexRebalancer | OnChain | Weighted basket rebalancing |

---

## 🔑 Configuration des Clés API (fichier `.env`)

**Toutes les clés API sont centralisées dans un seul fichier : `.env`**

```bash
# Copier le template
cp .env.example .env
```

Contenu du `.env` :
```env
# ── TELEGRAM ──
TELEGRAM_BOT_TOKEN=votre_token_ici
TELEGRAM_CHAT_ID=votre_chat_id_ici

# ── BITGET ──
BITGET_API_KEY=votre_cle_ici
BITGET_API_SECRET=votre_secret_ici
BITGET_API_PASSWORD=votre_password_ici

# ── MEXC ──
MEXC_API_KEY=votre_cle_ici
MEXC_API_SECRET=votre_secret_ici

# ── BLOCKCHAIN ──
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/VOTRE_CLE
ETH_PRIVATE_KEY=votre_cle_privee_ici
ETH_WALLET_ADDRESS=votre_adresse_ici
```

> ⚠️ **Le fichier `.env` est dans le `.gitignore`** — il ne sera jamais commité.

### Comment ça marche ?

| Module | Méthode de lecture |
|--------|-------------------|
| **Freqtrade** | Les JSON configs pointent vers `.env`. Remplissez les champs `key`/`secret` dans le JSON OU laissez vides et utilisez le `.env` |
| **Hummingbot** | Les scripts lisent d'abord le YAML config, puis fallback sur `.env` via `env_loader` |
| **OnChain** | Les configs Python lisent directement depuis `.env` via `os.environ.get()` |
| **Telegram** | Lu automatiquement depuis `.env` par `TelegramNotifier` |

---

## 🧪 Testing

```bash
# All tests
python -m pytest freqtrade/tests/ hummingbot/tests/ onchain/tests/ -v

# Specific module
python -m pytest freqtrade/tests/test_all_strategies.py -v
```

---

## 📦 Shared Utilities

All strategies share these modules (imported via `utils/`):

| Module | Purpose |
|--------|---------|
| `TradeLogger` | SQLite (per-strategy table) + CSV backup, thread-safe |
| `TelegramNotifier` | Rate-limited alerts, trade/error/startup messages |
| `PerformanceTracker` | Win rate, PnL, drawdown, weekly reports |
| `CommonIndicators` | RSI, EMA, BB, ATR, ADX, MACD, Volume, Breakout |
