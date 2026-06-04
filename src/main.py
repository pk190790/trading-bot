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
        logging.FileHandler("logs/trades.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

exchange = bc.create_exchange()


def run_bot() -> None:
    try:
        df = bc.get_ohlcv(exchange, SYMBOL, TIMEFRAME, limit=150)
        df = calculate_supertrend(df, atr_period=ATR_PERIOD, multiplier=ATR_MULTIPLIER)
        signal = get_latest_signal(df)

        last_candle = df.index[-1]
        trend = "LONG" if df["trend"].iloc[-1] == 1 else "SHORT"
        logger.info(f"[{last_candle}] Trend: {trend} | Signal: {signal or 'none'}")

        if signal:
            handle_signal(exchange, signal)

    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)


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
