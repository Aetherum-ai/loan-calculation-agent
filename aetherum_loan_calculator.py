import pandas as pd
import requests
import datetime
from cmc_fetcher import fetch_data_app


def fetch_data():
    """Fetches real-time cryptocurrency data from CoinMarketCap API."""
    try:
       return fetch_data_app()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_risk_tier(df):
    """Calculates the risk tier based on volatility and market cap."""
    df['Volatility Score'] = (
        df['24h Change (%)'].abs() +
        df['7d Change (%)'].abs() / 7 +
        df['30d Change (%)'].abs() / 30 +
        df['90d Change (%)'].abs() / 90
    )
    df['Market Cap Rank'] = df['Market Cap'].rank(ascending=False)
    df['Risk Score'] = df['Volatility Score'] * df['Market Cap Rank']
    df['Risk Tier'] = pd.qcut(df['Risk Score'], q=4, labels=['Tier 1', 'Tier 1.5', 'Tier 2', 'Tier 3'])
    return df

def get_crypto_historical_data(coin_id, vs_currency, days):
    """Fetches historical cryptocurrency data for a given number of days."""
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    from_timestamp = int(start_date.timestamp())
    to_timestamp = int(end_date.timestamp())
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {"vs_currency": vs_currency, "from": from_timestamp, "to": to_timestamp}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        prices = data.get('prices', [])
        df_prices = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df_prices['timestamp'] = pd.to_datetime(df_prices['timestamp'], unit='ms')
        df_prices = df_prices.set_index('timestamp')
        return df_prices
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {coin_id}: {e}")
        return None

def get_crypto_correlation_matrix(crypto_symbols, vs_currency="usd", days=90):
    """Calculates the correlation matrix for a list of cryptocurrencies."""
    all_prices = pd.DataFrame()
    coin_id_map = {
        'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 'XRP': 'ripple',
        'LINK': 'chainlink', 'DOT': 'polkadot', 'ADA': 'cardano', 'AVAX': 'avalanche-2'
    }
    for symbol in crypto_symbols:
        coin_id = coin_id_map.get(symbol.upper())
        if not coin_id:
            continue
        df_crypto = get_crypto_historical_data(coin_id, vs_currency, days)
        if df_crypto is not None and not df_crypto.empty:
            df_crypto_daily = df_crypto['price'].resample('D').mean()
            all_prices[symbol] = df_crypto_daily
    all_prices = all_prices.dropna()
    if all_prices.empty:
        return None
    return all_prices.corr()

def assign_base_ltv_from_tier(tier):
    """Assigns a base LTV based on the risk tier."""
    tier_ltv_map = {'Tier 1': 0.70, 'Tier 1.5': 0.60, 'Tier 2': 0.50, 'Tier 3': 0.40}
    return tier_ltv_map.get(str(tier), 0.30)

def calculate_all_ltv_adjustments(df, correlation_matrix, portfolio):
    """Adjusts the baseline LTV based on volatility and correlation."""
    portfolio_symbols = list(portfolio.keys())
    df = df[df['Symbol'].isin(portfolio_symbols)]
    vol_scores = df['Volatility Score']
    vol_75 = vol_scores.quantile(0.75)
    vol_25 = vol_scores.quantile(0.25)
    adjusted_ltvs = {}
    for _, row in df.iterrows():
        symbol = row['Symbol']
        tier = row['Risk Tier']
        base_ltv = assign_base_ltv_from_tier(tier)
        ltv = base_ltv
        if row['Volatility Score'] > vol_75:
            ltv = max(0.2, ltv - 0.05)
        elif row['Volatility Score'] < vol_25:
            ltv = min(0.85, ltv + 0.02)
        if correlation_matrix is not None and symbol in correlation_matrix.columns:
            correlations = correlation_matrix[symbol].drop(symbol)
            if not correlations.empty:
                avg_corr = correlations.abs().mean()
                if avg_corr > 0.8:
                    ltv -= 0.05
                elif avg_corr < 0.5:
                    ltv += 0.02
        adjusted_ltvs[symbol] = max(0.2, min(ltv, 0.85))
    return adjusted_ltvs

def calculate_aetherum_loan(portfolio, df):
    """Calculates the Aetherum loan details."""
    df = calculate_risk_tier(df)
    portfolio_symbols = list(portfolio.keys())
    correlation_matrix = get_crypto_correlation_matrix(portfolio_symbols)
    adjusted_ltvs = calculate_all_ltv_adjustments(df, correlation_matrix, portfolio)
    total_value = sum(portfolio.values())
    weighted_ltv = sum((portfolio[symbol] * adjusted_ltvs[symbol]) / total_value for symbol in portfolio_symbols)
    loan_amount = total_value * weighted_ltv
    risk_premiums = {'Tier 1': 0.04, 'Tier 1.5': 0.045, 'Tier 2': 0.05, 'Tier 3': 0.06}
    base_rate = 0.03
    weighted_interest_rate = sum(
        (portfolio[symbol] * (base_rate + risk_premiums.get(df[df['Symbol'] == symbol]['Risk Tier'].iloc[0], 0.07))) / total_value
        for symbol in portfolio_symbols
    )
    return {
        "loan_amount": loan_amount,
        "weighted_ltv": weighted_ltv,
        "interest_rate": weighted_interest_rate
    }