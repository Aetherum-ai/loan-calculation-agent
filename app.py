from dotenv import load_dotenv
import streamlit as st
from agent import run_finance_agent
import os
import pandas as pd
import json
from portfolios import SAMPLE_PORTFOLIOS
import datetime
from cmc_fetcher import fetch_data_app

load_dotenv()

API_KEY = os.getenv("CMC_API_KEY")
os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
os.environ['PHI_API_KEY'] = os.getenv("PHI_API_KEY")

def fetch_data():
    """Fetch data for the top 100 cryptocurrencies from CoinMarketCap."""
    return fetch_data_app()


# -------- LOGIC from loan_calc4.py: LTV & INTEREST RULES --------
def classify_risk(symbol, vol, mcap):
    """Classify asset risk into tiers based on volatility and market cap."""
    if vol < 3 and mcap > 1e10:
        return "Tier 1"
    elif vol < 6 and mcap > 5e9:
        return "Tier 1.5"
    elif vol < 10:
        return "Tier 2"
    else:
        return "Tier 3"

def ltv_by_risk(tier, vol):
    """Determine Loan-to-Value (LTV) based on risk tier and volatility."""
    base = {'Tier 1': 70, 'Tier 1.5': 65, 'Tier 2': 55, 'Tier 3': 45}
    adj = 0
    if vol > 7:
        adj = -5
    elif vol < 2:
        adj = +2
    return max(0, base.get(tier, 50) + adj)

def interest_by_risk(tier, vol):
    """Determine interest rate based on risk tier and volatility."""
    base_rate = 3.0  # Base risk-free rate
    premium = {'Tier 1': 4, 'Tier 1.5': 4.5, 'Tier 2': 5, 'Tier 3': 6}
    adj = 1 if vol > 10 else 0
    return base_rate + premium.get(tier, 5) + adj

def calculate_aetherum_loan(selected_tokens, user_portfolio, df, months, should_show_df_result=True):
    """Calculate loan metrics based on the rules from loan_calc4.py."""
    results = []
    total_collateral = 0
    total_loan = 0
    total_interest_amount = 0

    for symbol in selected_tokens:
        if symbol not in df['Symbol'].values:
            continue

        coin = df[df['Symbol'] == symbol].iloc[0]
        vol = abs(coin['24h Change (%)'])
        mcap = coin['Market Cap']
        portfolio_amount = user_portfolio.get(symbol, 0)

        tier = classify_risk(symbol, vol, mcap)
        ltv = ltv_by_risk(tier, vol)
        interest = interest_by_risk(tier, vol)
        loan_amount = portfolio_amount * ltv / 100
        interest_amount = loan_amount * interest / 100

        results.append({
            "Asset": symbol,
            "Risk Tier": tier,
            "24h Vol (%)": f"{vol:.2f}",
            "LTV (%)": ltv,
            "Interest Rate (%)": interest,
            "Collateral ($)": f"${portfolio_amount:,.2f}",
            "Loan Amount ($)": f"${loan_amount:,.2f}"
        })

        total_collateral += portfolio_amount
        total_loan += loan_amount
        total_interest_amount += interest_amount

    df_result = pd.DataFrame(results)

    if total_collateral > 0 and total_loan > 0:
        portfolio_ltv = (total_loan / total_collateral) * 100
        weighted_interest = (total_interest_amount / total_loan) * 100
        liquidation_ltv = portfolio_ltv * 1.2
        expense_ratio = 0.05  # Fixed 5% from loan_calc4.py
        emi = (total_loan * (1 + weighted_interest / 100)) / months
    else:
        portfolio_ltv, weighted_interest, liquidation_ltv, expense_ratio, emi = 0, 0, 0, 0, 0

    summary = {
        "total_collateral": total_collateral,
        "total_loan": total_loan,
        "portfolio_ltv": portfolio_ltv,
        "liquidation_ltv": liquidation_ltv,
        "weighted_interest": weighted_interest,
        "expense_ratio": expense_ratio,
        "emi": emi
    }

    if should_show_df_result:
        summary['df_result'] = df_result
    else:
        summary['result'] = results

    return summary

def calculate_loan_api(totalPortfolioValue, listOfSelectedTokens, months, payout, inception_date, bank):
    
    # TOTAL_PORTFOLIO_VALUE = 1_000_000  # Fixed $1M total portfolio value
    TOTAL_PORTFOLIO_VALUE = totalPortfolioValue
    
    portfolio_type = "Custom"

    # --- Real-time Crypto Data ---
    market_df = fetch_data()
    if market_df.empty:
        raise Exception("Error while fetching market data.")

    # Update portfolio based on selection
    if portfolio_type == "Custom":
        # available_tokens = market_df['Symbol'].tolist()
        # selected_tokens = available_tokens[:4] # Default to first 4 tokens
        selected_tokens = listOfSelectedTokens

        if selected_tokens:
            num_tokens = len(selected_tokens)
            allocations = {}
            # Default to equal allocation
            for token in selected_tokens:
                allocations[token] = 100 / num_tokens
            
            # Convert percentages to amounts
            user_portfolio = {
                token: (percentage / 100) * TOTAL_PORTFOLIO_VALUE 
                for token, percentage in allocations.items()
            }
        else:
            user_portfolio = {} # Empty portfolio if no tokens are selected
            raise Exception("Please select at least one token.")

    else:
        user_portfolio = SAMPLE_PORTFOLIOS[portfolio_type]
        selected_tokens = list(user_portfolio.keys())


    # "Loan Input"

    inception_date = pd.Timestamp(inception_date)

    if user_portfolio:
        # --- Aetherum AI Agent Calculation ---
        total_collateral = sum(user_portfolio.values())
        prompt = f"""
        The user has:
        {chr(10).join([f"${amount:,.2f} in {symbol}" for symbol, amount in user_portfolio.items()])}
        Total Collateral = ${total_collateral:,.2f}

        Loan parameters:
        - Loan Length: {months} months
        - Payout Currency: {payout}
        - Inception Date: {inception_date}
        - Bank: {bank}
        """
        agent_response, loan_metrics = run_finance_agent(prompt)
        
        # if ~isinstance(loan_metrics, dict):
        #     raise Exception("Failed to calculate loan metrics from AI Agent.")
        
        ###

        # --- Aetherum (Hard-coded Rules) Loan Calculation ---
        aetherum_loan_details = calculate_aetherum_loan(selected_tokens, user_portfolio, market_df, months, False)

        return {
            "agent_response": agent_response,
            "loan_metrics": loan_metrics,
            "aetherum_loan_details": aetherum_loan_details
        }

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
    market_df = fetch_data()
    if not market_df.empty:
        st.dataframe(market_df)
    else:
        st.info("Could not fetch market data.")

    # Update portfolio based on selection
    if portfolio_type == "Custom":
        available_tokens = market_df['Symbol'].tolist()
        selected_tokens = st.multiselect(
            "Select tokens for your portfolio:",
            available_tokens,
            default=available_tokens[:4] # Default to first 4 tokens
        )

        if selected_tokens:
            st.subheader("Portfolio Allocation")
            num_tokens = len(selected_tokens)
            allocations = {}
            # Default to equal allocation
            for token in selected_tokens:
                allocations[token] = 100 / num_tokens
            
            # Convert percentages to amounts
            user_portfolio = {
                token: (percentage / 100) * TOTAL_PORTFOLIO_VALUE 
                for token, percentage in allocations.items()
            }
        else:
            user_portfolio = {} # Empty portfolio if no tokens are selected
            st.warning("Please select at least one token.")

    else:
        user_portfolio = SAMPLE_PORTFOLIOS[portfolio_type]
        selected_tokens = list(user_portfolio.keys())
        st.info(f"Using pre-defined {portfolio_type} portfolio.")

    # Display selected portfolio
    if user_portfolio:
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

        if submit and user_portfolio:
            # --- Aetherum AI Agent Calculation ---
            total_collateral = sum(user_portfolio.values())
            prompt = f"""
            The user has:
            {chr(10).join([f"${amount:,.2f} in {symbol}" for symbol, amount in user_portfolio.items()])}
            Total Collateral = ${total_collateral:,.2f}

            Loan parameters:
            - Loan Length: {months} months
            - Payout Currency: {payout}
            - Inception Date: {inception_date}
            - Bank: {bank}
            """
            agent_response, loan_metrics = run_finance_agent(prompt)
            
            st.header("Aetherum AI Agent Loan Calculator")
            if isinstance(loan_metrics, dict):
                if 'timestamp' in loan_metrics:
                    cache_time = datetime.datetime.fromtimestamp(loan_metrics['timestamp'])
                    st.info(f"Using cached results from {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"**Portfolio Value:** ${loan_metrics.get('portfolio_value', 0):,.2f}")
                st.write(f"**Loan Amount:** ${loan_metrics.get('loan_amount', 0):,.2f}")
                st.write(f"**Weighted LTV:** {loan_metrics.get('weighted_ltv', 0):.2%}")
                st.write(f"**Liquidation LTV:** {loan_metrics.get('liquidation_ltv', 0):.2%}")
                st.subheader("Market Analysis and Interest Rate")
                st.markdown(agent_response, unsafe_allow_html=True)
            else:
                st.error("Failed to calculate loan metrics from AI Agent.")
            
            st.divider()

            # --- Aetherum (Hard-coded Rules) Loan Calculation ---
            st.header("Aetherum Loan")
            aetherum_loan_details = calculate_aetherum_loan(selected_tokens, user_portfolio, market_df, months)

            st.subheader("Asset-Based Loan Breakdown")
            st.dataframe(aetherum_loan_details["df_result"])

            st.subheader("Final Loan Details")
            st.write(f"**Total Collateral Selected:** ${aetherum_loan_details['total_collateral']:,.2f}")
            st.write(f"**Total Loan Amount:** ${aetherum_loan_details['total_loan']:,.2f}")
            st.write(f"**Portfolio LTV:** {aetherum_loan_details['portfolio_ltv']:.2f}%")
            st.write(f"**Liquidation LTV:** {aetherum_loan_details['liquidation_ltv']:.2f}%")
            st.write(f"**Interest Rate:** {aetherum_loan_details['weighted_interest']:.2f}%")
            st.write(f"**Expense Ratio:** {aetherum_loan_details['expense_ratio']*100:.2f}%")
            st.write(f"**Monthly EMI:** ${aetherum_loan_details['emi']:,.2f}")


if __name__ == "__main__":
    main()
