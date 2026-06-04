import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "5"))
MAX_TRADE_USDT = float(os.getenv("MAX_TRADE_USDT", "100"))
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "10"))
ATR_MULTIPLIER = float(os.getenv("ATR_MULTIPLIER", "3.0"))
