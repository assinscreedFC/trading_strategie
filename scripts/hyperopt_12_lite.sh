#!/bin/bash
# Hyperopt 12 nouvelles strategies Lite — 100 epochs chacune
# IS: 20230101-20251130, Spaces: buy sell, Loss: SharpeHyperOptLossDaily

STRATEGIES=(
    ZScoreMeanReversionLite
    BollingerMACDReversalLite
    StochasticMomentumIndexLite
    ChoppinessBreakoutLite
    KeltnerChannelMomentumLite
    DMICrossoverLite
    ChandelierExitLite
    SuperTrendADXLite
    MoneyFlowIndexLite
    AwesomeOscillatorLite
    TripleScreenElderLite
    CCIMomentumTrendLite
)

CONFIG="freqtrade/config_backtest_kraken.json"
TIMERANGE="20230101-20251130"
EPOCHS=100
STRATEGY_PATH="freqtrade/strategies"

for strat in "${STRATEGIES[@]}"; do
    echo "=============================="
    echo "HYPEROPT: $strat ($(date))"
    echo "=============================="
    rtk freqtrade hyperopt \
        --config "$CONFIG" \
        --strategy "$strat" \
        --strategy-path "$STRATEGY_PATH" \
        --timerange "$TIMERANGE" \
        --epochs "$EPOCHS" \
        --spaces buy sell \
        --hyperopt-loss SharpeHyperOptLossDaily \
        --timeframe 4h \
        -j -1 2>&1 | tail -20
    
    echo ""
    echo "Exporting best params for $strat..."
    rtk freqtrade hyperopt-show --best \
        --config "$CONFIG" \
        --strategy "$strat" \
        --strategy-path "$STRATEGY_PATH" \
        --no-header 2>&1 | tail -15
    echo ""
done

echo "=============================="
echo "ALL DONE — $(date)"
echo "=============================="
