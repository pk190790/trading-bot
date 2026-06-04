import logging
import ccxt
from src import binance_client as bc
from src.config import MAX_LEVERAGE, MAX_TRADE_USDT, SYMBOL

logger = logging.getLogger(__name__)


def handle_signal(exchange: ccxt.binanceusdm, signal: str) -> None:
    """Executes a BUY or SELL signal with position management."""
    open_pos = bc.get_open_position(exchange, SYMBOL)

    if signal == "BUY":
        if open_pos and float(open_pos.get("contracts", 0)) > 0:
            logger.info("BUY signal received but long position already open — skipping")
            return

        # Close any open short first
        if open_pos and float(open_pos.get("contracts", 0)) < 0:
            logger.info("Closing existing SHORT before opening LONG")
            bc.place_market_order(exchange, SYMBOL, "buy", abs(float(open_pos["notional"])))

        balance = bc.get_usdt_balance(exchange)
        trade_usdt = min(MAX_TRADE_USDT, balance * 0.1)

        if trade_usdt < 5:
            logger.warning(f"Balance too low to trade: {balance:.2f} USDT")
            return

        bc.set_leverage(exchange, SYMBOL, MAX_LEVERAGE)
        order = bc.place_market_order(exchange, SYMBOL, "buy", trade_usdt)
        logger.info(f"LONG opened: {order['id']}")

    elif signal == "SELL":
        if open_pos and float(open_pos.get("contracts", 0)) < 0:
            logger.info("SELL signal received but short position already open — skipping")
            return

        # Close any open long first
        if open_pos and float(open_pos.get("contracts", 0)) > 0:
            logger.info("Closing existing LONG before opening SHORT")
            bc.place_market_order(exchange, SYMBOL, "sell", abs(float(open_pos["notional"])))

        balance = bc.get_usdt_balance(exchange)
        trade_usdt = min(MAX_TRADE_USDT, balance * 0.1)

        if trade_usdt < 5:
            logger.warning(f"Balance too low to trade: {balance:.2f} USDT")
            return

        bc.set_leverage(exchange, SYMBOL, MAX_LEVERAGE)
        order = bc.place_market_order(exchange, SYMBOL, "sell", trade_usdt)
        logger.info(f"SHORT opened: {order['id']}")
