from flask import Flask, render_template
import yfinance as yf
from newsapi import NewsApiClient
from textblob import TextBlob
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy_financial as npf

app = Flask(__name__)

# Initialize News API client (replace 'YOUR_API_KEY' with your actual API key)
newsapi = NewsApiClient(api_key=YOUR_API_KEY)

def fetch_financial_statements(stock_symbol):
    try:
        # Fetch financial statements data from Yahoo Finance
        income_statement = yf.Ticker(stock_symbol).income_stmt
        balance_sheet = yf.Ticker(stock_symbol).balance_sheet
        cash_flow_statement = yf.Ticker(stock_symbol).cash_flow
        return income_statement, balance_sheet, cash_flow_statement
    
    except Exception as e:
        print(f"Error fetching financial statements: {e}")
        return None, None, None

def derive_listing_country(stock_symbol):
    # Fetch stock information to determine the country of listing
    stock_info = yf.Ticker(stock_symbol).info
    listing_country = stock_info['country']
    return listing_country

def calculate_discount_rate(listing_country):
    # Determine the appropriate risk-free rate based on the country of listing
    if listing_country == 'United States':
        # Use the yield of 10-year Treasury bonds as the risk-free rate
        risk_free_rate = 0.025  # 2.5% as an example
    # Add more countries and their corresponding risk-free rates as needed
    else:
        risk_free_rate = 0.03  # Default risk-free rate
    return risk_free_rate


def calculate_dcf_valuation(cash_flow_statement, risk_free_rate):
    fcf = cash_flow_statement.T
    fcf = fcf["Free Cash Flow"].T
    print(fcf)
    # Discount future cash flows to present value
    present_value = npf.npv(risk_free_rate, fcf)

    # Return the DCF valuation
    return present_value

def fetch_market_valuation(stock_symbol):
    # Fetch market data such as current price
    stock_data = yf.Ticker(stock_symbol).history(period='1d')
    current_price = stock_data['Close'].iloc[-1]
    return current_price

def compare_valuations(dcf_valuation, market_valuation):
    # Compare DCF valuation with market valuation
    percentage_difference = ((market_valuation - dcf_valuation) / dcf_valuation) * 100
    return percentage_difference

def determine_recommendation(comparison_result):
    # Determine buy/sell/hold recommendation based on valuation comparison
    if comparison_result > 10:
        return 'Sell', abs(comparison_result)
    elif comparison_result < -10:
        return 'Buy', abs(comparison_result)
    else:
        return 'Hold', 0

@app.route('/')
def index():
    try:
        # Stock symbol
        stock_symbol = 'MSFT'

        # Fetch financial statements
        income_statement, balance_sheet, cash_flow_statement = fetch_financial_statements(stock_symbol)

        # Derive listing country
        listing_country = derive_listing_country(stock_symbol)

        # Calculate discount rate
        risk_free_rate = calculate_discount_rate(listing_country)

        # Perform DCF valuation
        dcf_valuation = calculate_dcf_valuation(cash_flow_statement, risk_free_rate)

        # Fetch market valuation
        market_valuation = fetch_market_valuation(stock_symbol)*balance_sheet.loc["Ordinary Shares Number"][0]

        # Compare valuations
        comparison_result = compare_valuations(dcf_valuation, market_valuation)

        # Determine recommendation
        recommendation, percentage_difference = determine_recommendation(comparison_result)

        # Fetch historical data for MSFT from Yahoo Finance
        stock_data = yf.download(stock_symbol, start='2019-01-01', end='2022-01-01')

        # Calculate Moving Averages
        stock_data['MA_20'] = stock_data['Close'].rolling(window=20).mean()
        stock_data['MA_50'] = stock_data['Close'].rolling(window=50).mean()

        # Calculate Relative Strength Index (RSI)
        delta = stock_data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        RS = gain / loss
        RSI = 100 - (100 / (1 + RS))
        stock_data['RSI'] = RSI

        # Plot closing prices and Moving Averages
        plt.figure(figsize=(10, 6))
        plt.plot(stock_data.index, stock_data['Close'], label='Closing Price')
        plt.plot(stock_data.index, stock_data['MA_20'], label='MA 20 Days')
        plt.plot(stock_data.index, stock_data['MA_50'], label='MA 50 Days')
        plt.title(f'{stock_symbol} Stock Analysis')
        plt.xlabel('Date')
        plt.ylabel('Price (USD)')
        plt.legend()
        plt.xticks(rotation=45)

        # Save the plot as a temporary file
        plt.savefig('static/stock_graph.png')
        plt.close()

        # Calculate the date 15 days ago
        date_15_days_ago = datetime.now() - timedelta(days=15)
        date_15_days_ago_str = date_15_days_ago.strftime("%Y-%m-%d")

        # Fetch news articles related to AAPL from News API
        articles = newsapi.get_everything(q=stock_symbol, from_param=date_15_days_ago_str, language='en', sort_by='publishedAt')

        # Perform sentiment analysis on news articles and aggregate sentiment score
        total_sentiment_score = 0
        for index, article in enumerate(articles['articles'], start=1):
            if article['description'] is not None:
                sentiment_score = TextBlob(article['description']).sentiment.polarity
                # Weighted sentiment score by index
                total_sentiment_score += sentiment_score * (1 / index)

        # Determine buy/sell/hold recommendation based on aggregated sentiment score
        if total_sentiment_score > 0:
            news_recommendation = "Buy"
        elif total_sentiment_score < 0:
            news_recommendation = "Sell"
        else:
            news_recommendation = "Hold"

        return render_template('index.html', recommendation=recommendation, percentage_difference=percentage_difference,
                               stock_data=stock_data, articles=articles['articles'], news_recommendation=news_recommendation)

    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
