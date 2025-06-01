TOTAL_PORTFOLIO_VALUE = 1_000_000

SAMPLE_PORTFOLIOS = {
    "Conservative": {
        "BTC": 0.8 * TOTAL_PORTFOLIO_VALUE,  # 80%
        "ETH": 0.2 * TOTAL_PORTFOLIO_VALUE   # 20%
    },
    "Moderate": {
        "BTC": 0.5 * TOTAL_PORTFOLIO_VALUE,  # 50%
        "ETH": 0.3 * TOTAL_PORTFOLIO_VALUE,  # 30%
        "SOL": 0.2 * TOTAL_PORTFOLIO_VALUE   # 20%
    },
    "Aggressive": {
        "BTC": 0.4 * TOTAL_PORTFOLIO_VALUE,  # 40%
        "ETH": 0.3 * TOTAL_PORTFOLIO_VALUE,  # 30%
        "SOL": 0.2 * TOTAL_PORTFOLIO_VALUE,  # 20%
        "XRP": 0.1 * TOTAL_PORTFOLIO_VALUE   # 10%
    }
}