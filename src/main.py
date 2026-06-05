import logging
import time
import schedule
from src import binance_client as bc
from src.supertrend import calculate_supertrend, get_latest_signal
from src.order_handler import handle_signal
from src.config import SYMBOL, TIMEFRAME, ATR_PERIOD, ATR_MULTIPLIER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

exchange = None


def get_exchange():
    """Returns exchange, reconnects if needed."""
    global exchange
    if exchange is None:
        exchange = bc.create_exchange()
    return exchange


def run_bot() -> None:
    global exchange
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            ex = get_exchange()
            df = bc.get_ohlcv(ex, SYMBOL, TIMEFRAME, limit=150)
            df = calculate_supertrend(df, atr_period=ATR_PERIOD, multiplier=ATR_MULTIPLIER)
            signal = get_latest_signal(df)

            last_candle = df.index[-1]
            trend = "LONG" if df["trend"].iloc[-1] == 1 else "SHORT"
            logger.info(f"[{last_candle}] Trend: {trend} | Signal: {signal or 'none'}")

            if signal:
                handle_signal(ex, signal)
            return  # success

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{retries} failed: {e}")
            exchange = None  # force reconnect on next attempt
            if attempt < retries:
                time.sleep(10 * attempt)
            else:
                logger.error("All retries failed — will try again next tick.")


def get_schedule_interval(timeframe: str) -> int:
    """Returns check interval in seconds (checks twice per candle)."""
    mapping = {"1m": 30, "3m": 90, "5m": 150, "15m": 60, "30m": 120, "1h": 300, "4h": 600}
    return mapping.get(timeframe, 60)


if __name__ == "__main__":
    logger.info(f"Starting Supertrend Bot | {SYMBOL} | {TIMEFRAME}")
    run_bot()  # run immediately on start

    interval = get_schedule_interval(TIMEFRAME)
    logger.info(f"Scheduling checks every {interval}s")
    schedule.every(interval).seconds.do(run_bot)

    while True:
        schedule.run_pending()
        time.sleep(1)
