import yfinance as yf


def get_finance(symbol: str) -> dict:
    """Gets stock price and company information."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency"),
            "business_summary": (info.get("longBusinessSummary") or "")[:1000],
            "website": info.get("website"),
        }
    except Exception as e:
        return {"error": str(e)}
