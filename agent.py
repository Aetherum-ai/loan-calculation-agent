from dotenv import load_dotenv
from cache_utils import ResponseCache
import time 
import json
from cmc_fetcher import fetch_data_app

def run_finance_agent(prompt, allocations):
    from agno.models.groq import Groq
    from agno.agent import Agent
    from agno.tools.duckduckgo import DuckDuckGoTools
    from agno.tools.newspaper4k import Newspaper4kTools
    from textwrap import dedent
    import os
    import json
    import requests
    import pandas as pd
    import datetime
    import pickle
    from datetime import datetime, timedelta
    import datetime 

    load_dotenv()

    os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
    os.environ['PHI_API_KEY'] = os.getenv("PHI_API_KEY")

    def fetch_data():
        '''Use this function to fetch real-time cryptocurrency data from CoinMarketCap API.'''

        try:
            return fetch_data_app()
        except Exception as e:
            print(f"Error fetching data in agent: {e}")
          



    
    def calculate_risk_tier(df):
        '''
        Use this function to calculate the risk tier based on volatility and market cap. 
        '''
        #df = fetch_data()
        df['Volatility Score'] = (
            df['24h Change (%)'].abs() +
            df['7d Change (%)'].abs()/7 +
            df['30d Change (%)'].abs()/30 +
            df['90d Change (%)'].abs()/90
        )

        # Rank assets by market cap (higher cap = lower risk)
        df['Market Cap Rank'] = df['Market Cap'].rank(ascending=False)

        # Risk score: combine volatility and market cap ranking
        df['Risk Score'] = df['Volatility Score'] * df['Market Cap Rank']

        # Quantile-based tiering
        df['Risk Tier'] = pd.qcut(df['Risk Score'], q=4, labels=['Tier 1', 'Tier 1.5', 'Tier 2', 'Tier 3'])

        return df[['Symbol', 'Name', 'Last Price', '24h Change (%)', '7d Change (%)', '30d Change (%)', '90d Change (%)', 'Volatility Score', 'Market Cap', 'Risk Score', 'Risk Tier']]



    def get_crypto_historical_data(coin_id, vs_currency, days):
        """
        Fetches historical cryptocurrency data (price, market cap, volume) for a given number of days.

        """
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)

        # Convert dates to Unix timestamps (milliseconds for CoinGecko)
        from_timestamp = int(start_date.timestamp())
        to_timestamp = int(end_date.timestamp())

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": vs_currency,
            "from": from_timestamp,
            "to": to_timestamp
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            data = response.json()

            prices = data.get('prices', [])

            df_prices = pd.DataFrame(prices, columns=['timestamp', 'price'])

            # Convert timestamp to datetime
            df_prices['timestamp'] = pd.to_datetime(df_prices['timestamp'], unit='ms')
            df_prices = df_prices.set_index('timestamp')

            return df_prices

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {coin_id}: {e}")
            return None


    def get_crypto_correlation_matrix(crypto_symbols, vs_currency="usd", days=90):
        """
        Fetches historical price data for multiple cryptocurrencies and calculates their correlation matrix.

        """
        all_prices = pd.DataFrame()
        coin_id_map = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana',
            'XRP': 'ripple'
        }

        for symbol in crypto_symbols:
            coin_id = coin_id_map.get(symbol.upper())
            if not coin_id:
                print(f"Unknown cryptocurrency symbol: {symbol}. Skipping.")
                continue

            print(f"Fetching data for {symbol} ({coin_id})...")
            df_crypto = get_crypto_historical_data(coin_id, vs_currency, days)

            if df_crypto is not None and not df_crypto.empty:
                # Resample to daily to ensure consistent frequency for correlation
                df_crypto_daily = df_crypto['price'].resample('D').mean()
                all_prices[symbol] = df_crypto_daily
            else:
                print(f"Could not fetch data for {symbol}. Cannot calculate correlation.")
                return None

        # Drop rows with NaN values (e.g., if one crypto has missing data for a day)
        all_prices = all_prices.dropna()

        if all_prices.empty:
            print("No common historical data found for all cryptocurrencies to calculate correlation.")
            return None

        print("\nCalculating correlation matrix...")
        correlation_matrix = all_prices.corr()
        return correlation_matrix



    def assign_base_ltv_from_tier(tier):
        """
        Use this function to assign a base LTV based on the risk tier.
        """
        tier_ltv_map = {
            'Tier 1': 0.70,
            'Tier 1.5': 0.60,
            'Tier 2': 0.50,
            'Tier 3': 0.40
        }
        return tier_ltv_map.get(str(tier), 0.30)




    def calculate_all_ltv_adjustments(df, correlation_matrix, portfolio):
        """
        Refer to this function to make adjustments to the baseline LTV based on volatility and correlation. 
        """
        df = fetch_data()
        df = calculate_risk_tier(df)

        portfolio_symbols = list(portfolio.keys())

        df = df[df['Symbol'].isin(portfolio_symbols)]
        # Normalize volatility scores for percentile calculation
        vol_scores = df['Volatility Score']
        vol_75 = vol_scores.quantile(0.75)
        vol_25 = vol_scores.quantile(0.25)

        baseline_ltvs = {}
        adjusted_ltvs = {}

        for _, row in df.iterrows():
            symbol = row['Symbol']
            tier = row['Risk Tier']
            base_ltv = assign_base_ltv_from_tier(tier)
            baseline_ltvs[symbol] = base_ltv

            # Volatility adjustment
            vol_score = row['Volatility Score']
            ltv = base_ltv
            if vol_score > vol_75:
                ltv = max(0.2, ltv - 0.05)
            elif vol_score < vol_25:
                ltv = min(0.85, ltv + 0.02)

                    # Correlation adjustment
            if correlation_matrix is not None:
                try:
                    if isinstance(correlation_matrix, pd.DataFrame):
                        if symbol in correlation_matrix.columns:
                            correlations = correlation_matrix[symbol].drop(symbol)
                            if not correlations.empty:
                                avg_corr = correlations.abs().mean()
                                if avg_corr > 0.8:
                                    ltv -= 0.05
                                elif avg_corr < 0.5:
                                    ltv += 0.02
                    elif isinstance(correlation_matrix, dict):
                        if symbol in correlation_matrix:
                            # For dict format, assume values are correlation coefficients
                            correlations = [v for k, v in correlation_matrix[symbol].items() if k != symbol]
                            if correlations:
                                avg_corr = sum(abs(c) for c in correlations) / len(correlations)
                                if avg_corr > 0.8:
                                    ltv -= 0.05
                                elif avg_corr < 0.5:
                                    ltv += 0.02
                except Exception as e:
                    print(f"Warning: Error processing correlations for {symbol}: {e}")
                    # Continue with
            ltv = max(0.2, min(ltv, 0.85))
            adjusted_ltvs[symbol] = ltv
        return baseline_ltvs, adjusted_ltvs

    def calculate_loan_metrics(prompt_text):
        """Calculate loan metrics from the provided portfolio data"""
        # Parse portfolio data from prompt
        portfolio = {}
        for line in prompt_text.split('\n'):
            if '$' in line and 'in' in line:
                parts = line.split('$')[1].split('in')
                amount = float(parts[0].replace(',', '').strip())
                symbol = parts[1].strip()
                portfolio[symbol] = amount

        # Get market data and risk tiers
        df = fetch_data()
        df = calculate_risk_tier(df)
        
        # Get portfolio symbols and correlation matrix
        portfolio_symbols = list(portfolio.keys())
        correlation_matrix = get_crypto_correlation_matrix(portfolio_symbols)
        
        # Calculate LTVs and adjustments
        baseline_ltvs, adjusted_ltvs = calculate_all_ltv_adjustments(df, correlation_matrix, portfolio)
        
        # Calculate weighted LTV
        total_value = sum(portfolio.values())
        weighted_ltv = sum(
            (portfolio[symbol] * adjusted_ltvs[symbol]) / total_value 
            for symbol in portfolio.keys()
        )
        
        # Calculate loan details
        loan_amount = total_value * weighted_ltv
        liquidation_ltv = weighted_ltv * 1.2  # 120% of final LTV
        expense_ratio = 0.0005 * loan_amount  # 0.05% of loan amount
        
        return {
            # TODO: we need emi here as well,
            # we need to calculate the monthly EMI based on the loan amount, interest rate, and tenure
            # we need o return the interest rate as well
            # we also need the Interest Paid over the lifetime of the loan
            "portfolio_value": total_value,
            "weighted_ltv": weighted_ltv,
            "loan_amount": loan_amount,
            "liquidation_ltv": liquidation_ltv,
            "expense_ratio": expense_ratio,
            "risk_data": df[df['Symbol'].isin(portfolio_symbols)][['Symbol', 'Risk Tier', 'Volatility Score']].to_dict('records'),
            "correlation_matrix": correlation_matrix,
            "portfolio_metrics": {
                symbol: {
                    "amount": amount,
                    "baseline_ltv": baseline_ltvs[symbol],
                    "adjusted_ltv": adjusted_ltvs[symbol],
                    "allocation": allocations[symbol],
                }
                for symbol, amount in portfolio.items()
            }
        }

    df = fetch_data()
    loan_metrics = calculate_loan_metrics(prompt)
    portfolio = {}
    for line in prompt.split('\n'):
        if '$' in line and 'in' in line:
            parts = line.split('$')[1].split('in')
            amount = float(parts[0].replace(',', '').strip())
            symbol = parts[1].strip()
            portfolio[symbol] = amount


    research_agent = Agent(
        model=Groq(id="llama3-70b-8192"),
        tools=[DuckDuckGoTools(),
            Newspaper4kTools()

        ],  
        description=dedent("""\
                      You are a professional crypto financial analyst. Follow the given instructions to analyze the user's crypto portfolio and determine a fair and safe loan value based on real-time market conditions.

        """),
        instructions=dedent("""
                     Based on the provided pre-calculated loan metrics and market conditions:

            1. Search and analyze current crypto market news and trends
            2. Calculate the appropriate interest rate using:
               - Base rate (Federal funds rate): 4.33%
               - Aetherum premium: 2%
               - Risk premium based on provided risk tiers
               - Volatility premium (1% if volatility > 10%)
               
            3. Generate a detailed market analysis report
             
            
            DO NOT perform any LTV or loan amount calculations - use the provided values. 
                            
        """),
        expected_output=dedent("""\

           Im giving you the portfolio and loan details, just provide market analysis and interest rate.
        
            The format of the output should be:
        
            **Insights into the current market conditions**
              Under this section, provide a brief overview of the current market conditions of the coins owned by the user based on the latest news and trends.
            **Interest rate determined based on the current market conditions**
              Under this section, provide the interest rate determined based on the current market conditions, and the loan details.
            
                               
        """),
        markdown=True,
        show_tool_calls=True,
        add_datetime_to_instructions=True,
    )


    df = fetch_data()
    loan_metrics = calculate_loan_metrics(prompt)
    portfolio = {}
    for line in prompt.split('\n'):
        if '$' in line and 'in' in line:
            parts = line.split('$')[1].split('in')
            amount = float(parts[0].replace(',', '').strip())
            symbol = parts[1].strip()
            portfolio[symbol] = amount

      # Before caching the response, convert DataFrame objects to serializable format
    serializable_metrics = loan_metrics.copy()
    
    # Convert correlation matrix if it exists and is a DataFrame
    if 'correlation_matrix' in serializable_metrics and isinstance(serializable_metrics['correlation_matrix'], pd.DataFrame):
        serializable_metrics['correlation_matrix'] = serializable_metrics['correlation_matrix'].to_dict()

    # Add any other DataFrame conversions if needed
    if 'risk_data' in serializable_metrics:
        serializable_metrics['risk_data'] = [dict(row) for row in serializable_metrics['risk_data']]


    # Add caching logic here
    cache = ResponseCache()
    
    # Check cache first
    #cached_response, cached_metrics = cache.get_cached_response(prompt, portfolio, response_content, serializable_metrics)
    #if cached_response and cached_metrics:
    #    return cached_response, cached_metrics

    enhanced_prompt = f"""{prompt}

    Latest Market Data:
    {df[df['Symbol'].isin(portfolio.keys())].to_markdown()}

    Correlation Matrix:
    {loan_metrics['correlation_matrix'].to_markdown() if isinstance(loan_metrics['correlation_matrix'], pd.DataFrame) else json.dumps(loan_metrics['correlation_matrix'], indent=2)}

    Please analyze the current market conditions considering:
    1. The latest price movements and volatility metrics shown above
    2. Provide current market analysis and determine appropriate interest rate

    """

    response = research_agent.run(enhanced_prompt)
    response_content = getattr(response, "content", str(response))




    #with open("response.json", "w", encoding="utf-8") as f:
    #    json.dump({"content": getattr(response, "content", str(response))}, f, ensure_ascii=False, indent=2)
    cache.cache_response(prompt, portfolio, response_content, loan_metrics)
    
    return response_content, loan_metrics
