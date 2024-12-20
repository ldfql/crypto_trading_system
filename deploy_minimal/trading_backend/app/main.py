from fastapi import FastAPI
from app.services.trading.pair_selector import PairSelector
from app.services.market_analysis.market_data_service import MarketDataService

app = FastAPI(title="Crypto Trading System")

# Initialize services
market_data_service = MarketDataService()
pair_selector = PairSelector(market_data_service)

@app.get("/api/trading/pairs")
async def get_trading_pairs():
    """Get suitable trading pairs based on current market conditions."""
    pairs = await pair_selector.select_trading_pairs()
    return {"pairs": pairs}

@app.get("/")
async def root():
    return {"message": "Crypto Trading System API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
