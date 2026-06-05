import logging
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from src import binance_client as bc
from src.supertrend import calculate_supertrend, get_latest_signal
from src.order_handler import handle_signal
from src.config import SYMBOL, TIMEFRAME, ATR_PERIOD, ATR_MULTIPLIER, STOP_LOSS_PCT, TAKE_PROFIT_PCT
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(stream=__import__("sys").stdout)],
)
logger = logging.getLogger(__name__)

exchange = None
last_status = {"trend": "unknown", "signal": "none", "time": "never"}


def get_exchange():
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

            last_candle = str(df.index[-1])
            trend = "LONG" if df["trend"].iloc[-1] == 1 else "SHORT"
            logger.info(f"[{last_candle}] Trend: {trend} | Signal: {signal or 'none'}")

            last_status.update({"trend": trend, "signal": signal or "none", "time": last_candle})

            # Stop-Loss / Take-Profit prüfen
            check_sl_tp(ex)

            if signal:
                handle_signal(ex, signal)
            return

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{retries} failed: {e}")
            exchange = None
            if attempt < retries:
                time.sleep(10 * attempt)
            else:
                logger.error("All retries failed — will try again next tick.")


def check_sl_tp(ex) -> None:
    """Schließt Position wenn Stop-Loss oder Take-Profit erreicht."""
    if STOP_LOSS_PCT <= 0 and TAKE_PROFIT_PCT <= 0:
        return
    pos = bc.get_open_position(ex, SYMBOL)
    if not pos:
        return

    contracts = float(pos.get("contracts", 0))
    if contracts == 0:
        return

    entry = float(pos.get("entryPrice", 0))
    current = float(pos.get("markPrice", 0))
    side = "long" if contracts > 0 else "short"

    if entry == 0 or current == 0:
        return

    if side == "long":
        pnl_pct = (current - entry) / entry * 100
    else:
        pnl_pct = (entry - current) / entry * 100

    close_side = "sell" if side == "long" else "buy"
    notional = abs(float(pos.get("notional", 0)))

    if STOP_LOSS_PCT > 0 and pnl_pct <= -STOP_LOSS_PCT:
        logger.warning(f"STOP-LOSS ausgelöst! {pnl_pct:.2f}% | Entry: {entry:.2f} | Aktuell: {current:.2f}")
        bc.place_market_order(ex, SYMBOL, close_side, notional)

    elif TAKE_PROFIT_PCT > 0 and pnl_pct >= TAKE_PROFIT_PCT:
        logger.info(f"TAKE-PROFIT ausgelöst! +{pnl_pct:.2f}% | Entry: {entry:.2f} | Aktuell: {current:.2f}")
        bc.place_market_order(ex, SYMBOL, close_side, notional)


def get_schedule_interval(timeframe: str) -> int:
    mapping = {"1m": 30, "3m": 90, "5m": 150, "15m": 60, "30m": 120, "1h": 300, "4h": 600}
    return mapping.get(timeframe, 60)


# Minimal HTTP server so Railway sees an open port (keeps container alive)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            f"Supertrend Bot running\n"
            f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME}\n"
            f"Last check: {last_status['time']}\n"
            f"Trend: {last_status['trend']} | Signal: {last_status['signal']}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress HTTP logs


def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    logger.info(f"Starting Supertrend Bot | {SYMBOL} | {TIMEFRAME}")

    # Start health server in background thread
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    interval = get_schedule_interval(TIMEFRAME)
    logger.info(f"Checking every {interval}s")

    run_bot()  # run immediately on start

    while True:
        time.sleep(interval)
        run_bot()
