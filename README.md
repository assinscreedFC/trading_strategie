# Freqtrade Spot Trading Suite

Comprehensive cryptocurrency spot trading framework with Freqtrade, featuring 80+ technical analysis strategies, comprehensive backtesting tools, and performance monitoring utilities.

## Overview

This project provides a production-ready trading suite for spot trading across multiple crypto exchanges (Binance, Kraken, Bitget, MEXC). All strategies default to DRY_RUN mode for safety, and enforce spot-only trading with no leverage or short selling.

**Key characteristics:**
- 80+ technical indicator-based strategies
- Multi-exchange support (Binance, Kraken, Bitget, MEXC)
- Comprehensive backtesting and hyperparameter optimization
- Centralized API key management via .env
- Shared utilities for logging, performance tracking, and Telegram notifications
- Walk-forward analysis and regime detection
- SQLite + CSV trade logging per strategy

## Project Structure

```
ft_userdata/
├── freqtrade/                       # Freqtrade strategies and configurations
│   ├── config_binance.json          # Binance exchange configuration
│   ├── config_kraken.json           # Kraken exchange configuration
│   ├── config_bitget.json           # Bitget exchange configuration
│   ├── config_mexc.json             # MEXC exchange configuration
│   ├── config_dryrun_rsi.json       # Dry-run test configurations
│   ├── config_dryrun_smc.json       # Dry-run SMC-based strategy
│   ├── config_backtest_*.json       # Backtesting configurations
│   ├── strategies/                  # 80+ technical analysis strategies
│   │   ├── ADOSCTrailing.py         # ADOSC with trailing stop
│   │   ├── ADXRegimeFilter.py       # ADX-based regime filtering
│   │   ├── AroonCrossover.py        # Aroon oscillator crossover
│   │   ├── AwesomeOscillator*.py    # Awesome Oscillator variants
│   │   ├── BollingerMACD*.py        # Bollinger Bands + MACD combinations
│   │   ├── CCI*.py                  # Commodity Channel Index strategies
│   │   ├── Chandelier*.py           # Chandelier exit strategies
│   │   ├── [... 60+ more strategies ...]
│   │   └── {Strategy}.json          # Parameter files for each strategy
│   └── tests/
│       └── test_all_strategies.py   # Strategy validation tests
├── hummingbot/                      # Market-making and arbitrage scripts
│   ├── scripts/
│   │   ├── arbitrage_spatial.py     # Cross-exchange arbitrage
│   │   ├── arbitrage_triangulaire.py # Triangle arbitrage
│   │   ├── market_making_dex.py     # DEX market making
│   │   ├── order_flow_tracker.py    # Order flow analysis
│   │   ├── relative_value_rotation.py # Pair trading
│   │   ├── vwap_twap_execution.py   # VWAP/TWAP execution
│   │   ├── __init__.py
│   │   └── __pycache__
│   ├── configs/                     # YAML configuration files
│   └── tests/
├── onchain/                         # On-chain and DEX strategies
│   ├── scripts/
│   │   ├── sniper_bot.py            # DEX pool sniper
│   │   ├── whale_tracker.py         # Smart money copy trading
│   │   ├── index_rebalancer.py      # Portfolio rebalancing
│   │   ├── __init__.py
│   │   └── __pycache__
│   ├── configs/
│   └── tests/
├── scripts/                         # Analysis and backtesting tools
│   ├── batch_backtest.py            # Batch run multiple strategy backtests
│   ├── correlation_analysis.py      # Pair correlation analysis
│   ├── detect_regimes.py            # Market regime detection
│   ├── dry_run_audit.py             # Audit dry-run trades
│   ├── hyperopt_12_lite.sh          # Hyperparameter optimization script
│   ├── monte_carlo.py               # Monte Carlo analysis
│   ├── portfolio_allocator.py       # Portfolio allocation
│   ├── reclassify_oos.py            # Out-of-sample classification
│   ├── regime_tournament.py         # Strategy performance in regimes
│   └── walk_forward.py              # Walk-forward analysis
├── utils/                           # Shared utilities (zero duplication)
│   ├── __init__.py
│   ├── env_loader.py                # Centralized .env configuration loader
│   ├── logging_utils.py             # SQLite + CSV trade logging per strategy
│   ├── telegram_notifier.py         # Rate-limited Telegram alerts
│   ├── performance.py               # Performance metrics and weekly reports
│   └── indicators.py                # RSI, EMA, BB, ATR, ADX, MACD, etc.
├── user_data/                       # Freqtrade user directory
│   ├── backtest_results/            # Backtest result files
│   ├── data/                        # OHLCV market data
│   ├── freqaimodels/                # FreqAI model storage
│   ├── hyperopt_results/            # Hyperparameter optimization results
│   ├── hyperopts/                   # Hyperopt configuration files
│   ├── logs/                        # Trading logs
│   └── plot/                        # Backtest plots
├── reports/                         # Analysis reports
├── logs/                            # Trading logs and outputs
├── tests/                           # Test suite
├── .env                             # API keys (not committed)
├── .env.example                     # API key template
├── .gitignore
├── requirements.txt
├── RAPPORT_BACKTESTING.md           # Backtesting analysis report
└── README.md

```

## Installation

### Prerequisites
- Python 3.9+
- Git

### Setup

```bash
# Clone or download the repository
cd ft_userdata

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and fill in your API credentials
```

## Configuration

All API keys are centralized in a single `.env` file for security:

```bash
# Copy template to working .env
cp .env.example .env
```

**Required environment variables:**

```env
# Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Exchange APIs
BITGET_API_KEY=your_key
BITGET_API_SECRET=your_secret
BITGET_API_PASSWORD=your_password

MEXC_API_KEY=your_key
MEXC_API_SECRET=your_secret

# Blockchain (for on-chain strategies)
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ETH_WS_URL=wss://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
ETH_PRIVATE_KEY=your_private_key
ETH_WALLET_ADDRESS=your_wallet_address

# DEX Screener (optional)
DEXSCREENER_API_URL=https://api.dexscreener.com/latest/dex
```

**Important:** The `.env` file is in `.gitignore` and will never be committed to version control.

## Usage

### Running a Strategy (Dry-Run Mode - Default)

```bash
# All strategies start in DRY_RUN mode by default
freqtrade trade --strategy ADXRegimeFilter -c freqtrade/config_binance.json

# Test with specific configuration
freqtrade trade --strategy AroonCrossover -c freqtrade/config_dryrun_rsi.json
```

### Backtesting Strategies

```bash
# Backtest single strategy
freqtrade backtest --strategy ADOSCTrailing -c freqtrade/config_backtest_5pairs.json

# Run batch backtest on all strategies
python scripts/batch_backtest.py

# Backtest with hyperparameter optimization
freqtrade hyperopt --strategy BollingerMACDReversal -c freqtrade/config_binance.json --hyperopt-loss SharpeHyperOptLossDaily --epochs 100
```

### Analysis Tools

```bash
# Detect market regimes
python scripts/detect_regimes.py

# Correlation analysis
python scripts/correlation_analysis.py

# Walk-forward analysis
python scripts/walk_forward.py

# Monte Carlo analysis
python scripts/monte_carlo.py

# Portfolio allocation
python scripts/portfolio_allocator.py

# Dry-run audit
python scripts/dry_run_audit.py
```

### Running Tests

```bash
# Test all strategies
python -m pytest freqtrade/tests/ -v

# Test with coverage
python -m pytest freqtrade/tests/ --cov=freqtrade/strategies --cov-report=html
```

## Technology Stack

### Core Trading Engine
- **Freqtrade** (>=2024.1) - Cryptocurrency trading bot framework
- **CCXT** (>=4.0.0) - Unified cryptocurrency exchange API

### Data & Analysis
- **Pandas** (>=2.0.0) - Data manipulation and analysis
- **NumPy** (>=1.24.0) - Numerical computing
- **TA** (>=0.11.0) - Technical analysis indicators
- **ft-pandas-ta** (>=0.3.15) - Freqtrade technical analysis

### Machine Learning (Optional)
- **scikit-learn** (>=1.3.0) - Machine learning
- **XGBoost** (>=2.0.0) - Gradient boosting
- **PyTorch** (>=2.0.0) - Deep learning
- **torchvision** (>=0.15.0) - Computer vision (for chart analysis)

### On-Chain & DEX
- **Web3.py** (>=6.0.0) - Ethereum/blockchain interaction
- **aiohttp** (>=3.9.0) - Async HTTP client
- **websockets** (>=12.0) - WebSocket support

### Utilities
- **python-dotenv** (>=1.0.0) - Environment variable management
- **python-telegram-bot** (>=20.0) - Telegram notifications
- **PyYAML** (>=6.0) - YAML configuration parsing
- **SQLAlchemy** (>=2.0.0) - ORM for database operations
- **requests** (>=2.31.0) - HTTP library

### Testing
- **pytest** (>=7.4.0) - Testing framework
- **pytest-asyncio** (>=0.23.0) - Async testing support

## Shared Utilities

All strategies leverage these centralized modules:

| Module | Purpose |
|--------|---------|
| `env_loader.py` | Centralized .env configuration reader |
| `logging_utils.py` | SQLite + CSV trade logging per strategy |
| `telegram_notifier.py` | Rate-limited Telegram alerts and notifications |
| `performance.py` | Performance metrics, win rate, PnL tracking, weekly reports |
| `indicators.py` | Technical indicators: RSI, EMA, Bollinger Bands, ATR, ADX, MACD, etc. |

## Strategy Categories

### Technical Analysis Strategies (80+)
Indicators-based strategies including ADOSC, ADX, Aroon, Awesome Oscillator, Bollinger Bands, CCI, Chandelier, Choppiness, Keltner Channels, MACD, Momentum, Oscillators, Stochastic, and more.

Each strategy includes:
- Dynamic parameter optimization (.json files)
- RSI/momentum filters
- Support for multiple timeframes
- Risk management (position sizing, stop-loss)

### Market Making & Arbitrage (Hummingbot)
- **Arbitrage Spatial** - Cross-exchange spread capture
- **Arbitrage Triangulaire** - Single-exchange triangle cycles
- **Market Making DEX** - DEX market making (Uniswap V3)
- **Relative Value Rotation** - Pair trading with z-score
- **VWAP/TWAP Execution** - Volume-weighted execution with slicing
- **Order Flow Tracker** - Orderbook analysis and front-running detection

### On-Chain Strategies
- **Sniper Bot** - DEX pool sniping with safety checks
- **Whale Tracker** - Smart money copy trading
- **Index Rebalancer** - Weighted basket rebalancing

## Safety Features

- **DRY_RUN Default:** All strategies default to paper trading (no real capital at risk)
- **Spot-Only:** Zero leverage, no short selling (`can_short = False` enforced)
- **API Keys:** Blank placeholders in configs - fill them explicitly before live trading
- **Trade Logging:** Every trade logged to SQLite + CSV for audit trail
- **Telegram Alerts:** Configurable notifications for trades, errors, and status updates
- **Rate Limiting:** API request throttling to avoid exchange rate limits

## Database

Trade history and logs are stored in:
- **SQLite:** `logs/trades.db` (primary storage with SQL query support)
- **CSV:** `logs/{strategy_name}_trades.csv` (human-readable backup)

Per-strategy tables enable isolated analysis and performance tracking.

## Performance Reports

The system generates weekly performance reports including:
- Win rate percentage
- Profit factor
- Maximum drawdown
- Sharpe ratio
- Monthly returns
- Trade-by-trade PnL

## Backtesting Reports

Comprehensive backtesting analysis available in `RAPPORT_BACKTESTING.md`:
- Strategy comparison across market regimes
- Risk/return metrics
- Drawdown analysis
- Entry/exit quality analysis

## Development

### Code Organization Principles
- One utility per module (no duplication across strategies)
- DRY principle strictly enforced
- Centralized configuration via `.env` and JSON/YAML files
- SQLite for structured logging and easy querying
- Thread-safe implementation for Freqtrade compatibility

### Testing
- Unit tests for strategies: `freqtrade/tests/test_all_strategies.py`
- Integration tests for each module
- Use pytest with asyncio support

### Contributing
To add a new strategy:
1. Create `freqtrade/strategies/YourStrategy.py`
2. Create `freqtrade/strategies/YourStrategy.json` with parameters
3. Add unit test in `freqtrade/tests/test_all_strategies.py`
4. Document in strategy docstring
5. Run backtests to validate

## Production Deployment

Before deploying to production:
1. Backtest thoroughly across multiple market regimes
2. Walk-forward testing to validate out-of-sample performance
3. Start with very small capital and scale gradually
4. Monitor Telegram alerts closely
5. Review daily performance reports
6. Maintain dry-run parallel testing as a safety check

## Important Notes

- **All strategies default to DRY_RUN = true** - No real trades without explicit activation
- **API keys are blank placeholders** - Fill them before live trading
- **Database is SQLite** - Single file, no server needed, queryable
- **Exchange-specific configs** - Adjust settings for each exchange (fees, trading pairs, limits)
- **Linux/Mac recommended for production** - Better scheduling and monitoring support

## Troubleshooting

### ImportError when running strategies
Check that all dependencies are installed:
```bash
pip install -r requirements.txt
```

### API key issues
1. Verify `.env` file exists and contains your credentials
2. Check that you have created `.env` from `.env.example`
3. Verify API keys have correct permissions in exchange dashboard

### Backtest data issues
Freqtrade auto-downloads OHLCV data. Force refresh:
```bash
freqtrade download-data -c freqtrade/config_binance.json --refresh-pairs -t 1h 4h 1d
```

## Resources

- [Freqtrade Documentation](https://www.freqtrade.io/)
- [Hummingbot Documentation](https://hummingbot.org/)
- [Technical Analysis Library](https://github.com/bukosabino/ta)
- [Web3.py Documentation](https://web3py.readthedocs.io/)

## License

This project is provided as-is for educational and personal use. Always backtest thoroughly before live trading.

---

**Last Updated:** 2026-03-28
**Status:** Active development - 80+ strategies, regular updates
