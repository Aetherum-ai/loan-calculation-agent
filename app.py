import streamlit as st
from agent import run_finance_agent
import os
import pandas as pd
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import requests
import json
from portfolios import SAMPLE_PORTFOLIOS
import datetime



API_KEY = ""  # Replace with your CoinMarketCap key
os.environ['GROQ_API_KEY'] = ''
os.environ['PHI_API_KEY'] = ''
url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': API_KEY}
params = {'start': '1', 'limit': '100', 'convert': 'USD'}

# -------- USER PORTFOLIO --------
user_portfolio = {
    'BTC': 200_000,
    'ETH': 400_000,
    'SOL': 200_000,
    'XRP': 200_000
}

def fetch_historical_data(symbol, days=90):
    """Fetch historical price data from CoinGecko API"""
    # Map of common symbols to CoinGecko IDs
    coin_id_map = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'XRP': 'ripple',
        'LINK': 'chainlink',
        'DOT': 'polkadot',
        'ADA': 'cardano',
        'AVAX': 'avalanche-2'
    }
    
    coin_id = coin_id_map.get(symbol)
    if not coin_id:
        return None
        
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # Convert price data to DataFrame
        prices = data['prices']
        df = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return None

def fetch_data():
    res = requests.get(url, headers=headers, params=params)
    data = res.json()['data']
    return pd.DataFrame([{
        'Name': coin['name'],
        'Symbol': coin['symbol'],
        'Last Price': coin['quote']['USD']['price'],
        '24h Change (%)': coin['quote']['USD']['percent_change_24h'],
        '7d Change (%)': coin['quote']['USD']['percent_change_7d'],
        '30d Change (%)': coin['quote']['USD']['percent_change_30d'],
        '90d Change (%)': coin['quote']['USD']['percent_change_90d'],
        'Market Cap': coin['quote']['USD']['market_cap']
    } for coin in data if coin['symbol'] in user_portfolio])




def main():
    st.title("Finance Agent Streamlit App")

    
    TOTAL_PORTFOLIO_VALUE = 1_000_000  # Fixed $1M total portfolio value

    
    
    st.header("Portfolio Selection")
    portfolio_type = st.selectbox(
        "Select Portfolio Type",
        ["Custom"] + list(SAMPLE_PORTFOLIOS.keys()),
        index=0
    )

    # --- Real-time Crypto Data ---
    st.header("Real-Time Crypto Market Data")
    df = fetch_data()
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No data to display.")

    # Update portfolio based on selection
    if portfolio_type == "Custom":
        available_tokens = df['Symbol'].tolist()
        selected_tokens = st.multiselect(
            "Select tokens for your portfolio:",
            available_tokens,
            default=available_tokens[:2]
        )

        if selected_tokens:
            st.subheader("Portfolio Allocation")
            num_tokens = len(selected_tokens)
            
            # Initialize allocations dictionary
            allocations = {}
            remaining_percentage = 100
            
            # Create sliders for all but the last token
            for i, token in enumerate(selected_tokens[:-1]):
                max_allowed = remaining_percentage if i < len(selected_tokens)-1 else remaining_percentage
                allocation = st.slider(
                    f"{token} allocation (%)",
                    min_value=0,
                    max_value=max_allowed,
                    value=min(100 // num_tokens, max_allowed),
                    key=f"slider_{token}"
                )
                allocations[token] = allocation
                remaining_percentage -= allocation
            
            # Last token automatically gets the remaining percentage
            if selected_tokens:
                last_token = selected_tokens[-1]
                allocations[last_token] = remaining_percentage
                st.info(f"{last_token} allocation: {remaining_percentage}%")

            # Convert percentages to amounts
            user_portfolio = {
                token: (percentage / 100) * TOTAL_PORTFOLIO_VALUE 
                for token, percentage in allocations.items()
            }
    else:
        user_portfolio = SAMPLE_PORTFOLIOS[portfolio_type]
        selected_tokens = list(user_portfolio.keys())
        st.info(f"Using {portfolio_type} portfolio")

    # Display selected portfolio
    if 'user_portfolio' in locals():
        st.subheader("Selected Portfolio")
        portfolio_df = pd.DataFrame([
            {
                "Asset": k,
                "Allocation (%)": f"{(v/TOTAL_PORTFOLIO_VALUE)*100:.1f}%",
                "Amount ($)": f"${v:,.0f}"
            }
            for k, v in user_portfolio.items()
        ])
        st.table(portfolio_df)



    st.header("Loan Input")
    with st.form("loan_form"):
        col1, col2 = st.columns(2)
        months = col1.selectbox("Length of loan (months)", [6, 12, 24, 36])
        payout = col2.selectbox("Payout currency", ["USDC", "USDT", "USD"])

        col3, col4 = st.columns(2)
        inception_date = col3.date_input("Loan Inception Date", pd.Timestamp.today())
        bank = col4.selectbox("Select bank", ["American Bank", "Chase", "N26", "HSBC"])

        submit = st.form_submit_button("Calculate Loan")

        if submit:
            # Convert dictionary values to float
            user_portfolio = {k: float(v) for k, v in user_portfolio.items()}
            total_collateral = sum(user_portfolio.values())
            portfolio_df = df[df['Symbol'].isin(selected_tokens)]

            prompt = f"""
    The user has:
    {chr(10).join([f"${user_portfolio[sym]:,.2f} in {sym}" for sym in selected_tokens])}
    Total Collateral = ${total_collateral:,.2f}

    Loan parameters:
    - Loan Length: {months} months
    - Payout Currency: {payout}
    - Inception Date: {inception_date}
    - Bank: {bank}
    """
            response, loan_metrics = run_finance_agent(prompt)
            
            # Display loan details
            st.subheader("Loan Details")
            if isinstance(loan_metrics, dict):  # Add type check
                if 'timestamp' in loan_metrics:
                    cache_time = datetime.datetime.fromtimestamp(loan_metrics['timestamp'])
                    st.info(f"Using cached results from {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                st.write(f"Portfolio Value: ${loan_metrics['portfolio_value']:,.2f}")
                st.write(f"Loan Amount: ${loan_metrics['loan_amount']:,.2f}")
                st.write(f"Weighted LTV: {loan_metrics['weighted_ltv']:.2%}")
                st.write(f"Liquidation LTV: {loan_metrics['liquidation_ltv']:.2%}")
            else:
                st.error("Failed to calculate loan metrics")
            
            # Display market analysis
            st.subheader("Market Analysis and Interest Rate")
            st.markdown(response, unsafe_allow_html=True)


if __name__ == "__main__":
    main()