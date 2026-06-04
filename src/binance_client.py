import ccxt
import pandas as pd
import logging
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET

logger = logging.getLogger(__name__)

TESTNET_BASE = "https://testnet.binancefuture.com"

TESTNET_URLS = {
    "fapiPublic": f"{TESTNET_BASE}/fapi/v1",
    "fapiPublicV2": f"{TESTNET_BASE}/fapi/v2",
    "fapiPrivate": f"{TESTNET_BASE}/fapi/v1",
    "fapiPrivateV2": f"{TESTNET_BASE}/fapi/v2",
    "fapiPrivateV3": f"{TESTNET_BASE}/fapi/v3",
    "fapiData": f"{TESTNET_BASE}/futures/data",
}


def create_exchange() -> ccxt.binanceusdm:
    exchange = ccxt.binanceusdm({
        "apiKey": BINANCE_API_KEY,
        "secret": BINANCE_API_SECRET,
        "options": {
            "defaultType": "future",
            "fetchCurrencies": False,
        },
    })

    if BINANCE_TESTNET:
        exchange.urls["api"].update(exchange.urls["test"])
        logger.info("Connecting to Binance Futures TESTNET")
    else:
        logger.info("Connecting to Binance Futures LIVE")

    exchange.load_markets()
    return exchange


def get_ohlcv(exchange: ccxt.binanceusdm, symbol: str, timeframe: str, limit: int = 150) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def get_usdt_balance(exchange: ccxt.binanceusdm) -> float:
    balance = exchange.fetch_balance()
    return float(balance["USDT"]["free"])


def set_leverage(exchange: ccxt.binanceusdm, symbol: str, leverage: int) -> None:
    market_symbol = exchange.market_id(symbol)
    exchange.fapiPrivatePostLeverage({"symbol": market_symbol, "leverage": leverage})
    logger.info(f"Leverage set to {leverage}x for {symbol}")


def place_market_order(exchange: ccxt.binanceusdm, symbol: str, side: str, usdt_amount: float) -> dict:
    ticker = exchange.fetch_ticker(symbol)
    price = ticker["last"]
    market = exchange.market(symbol)
    amount_coin = usdt_amount / price
    amount_coin = exchange.amount_to_precision(symbol, amount_coin)

    order = exchange.create_order(
        symbol=symbol,
        type="market",
        side=side.lower(),
        amount=float(amount_coin),
    )
    logger.info(f"Order placed: {side} {amount_coin} {symbol} @ ~{price:.2f} USDT")
    return order


def get_open_position(exchange: ccxt.binanceusdm, symbol: str):
    positions = exchange.fetch_positions([symbol])
    for pos in positions:
        if float(pos["contracts"]) != 0:
            return pos
    return None
