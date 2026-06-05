"""
Supertrend Backtest
Holt historische OHLCV-Daten von Binance und simuliert alle Trades.

Usage:
    python backtest.py                          # BTC/USDT, 15m, 90 Tage
    python backtest.py --symbol ETH/USDT        # anderes Symbol
    python backtest.py --timeframe 1h           # anderer Zeitraum
    python backtest.py --days 180               # mehr History
    python backtest.py --capital 1000           # Startkapital
"""

import argparse
import ccxt
import pandas as pd
from src.supertrend import calculate_supertrend
from src.config import ATR_PERIOD, ATR_MULTIPLIER

MAX_LEVERAGE = 5
MAX_TRADE_USDT = 100


def fetch_historical(symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    exchange = ccxt.binanceusdm({
        "options": {"defaultType": "future", "fetchCurrencies": False},
    })
    exchange.urls["api"].update(exchange.urls["test"])

    # Approximate candle count
    tf_minutes = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_minutes.get(timeframe, 15)
    limit = min(int(days * 24 * 60 / minutes), 1500)

    print(f"Fetching {limit} candles for {symbol} ({timeframe})...")
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def run_backtest(symbol: str, timeframe: str, days: int, capital: float) -> None:
    df = fetch_historical(symbol, timeframe, days)
    df = calculate_supertrend(df, atr_period=ATR_PERIOD, multiplier=ATR_MULTIPLIER)

    balance = capital
    position = None  # {"side": "long"/"short", "entry": price, "size": usdt, "qty": coins}
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        price = row["close"]
        buy_signal = row["buy_signal"]
        sell_signal = row["sell_signal"]

        # Close existing position on opposite signal
        if position and ((buy_signal and position["side"] == "short") or
                         (sell_signal and position["side"] == "long")):
            entry = position["entry"]
            qty = position["qty"]
            if position["side"] == "long":
                pnl = (price - entry) * qty * MAX_LEVERAGE
            else:
                pnl = (entry - price) * qty * MAX_LEVERAGE

            balance += pnl
            trades.append({
                "close_time": df.index[i],
                "side": position["side"],
                "entry": entry,
                "exit": price,
                "size_usdt": position["size"],
                "pnl": pnl,
                "balance": balance,
            })
            position = None

        # Open new position
        if buy_signal and position is None:
            size = min(MAX_TRADE_USDT, balance * 0.1)
            qty = size / price
            position = {"side": "long", "entry": price, "size": size, "qty": qty}

        elif sell_signal and position is None:
            size = min(MAX_TRADE_USDT, balance * 0.1)
            qty = size / price
            position = {"side": "short", "entry": price, "size": size, "qty": qty}

    # Close open position at last price
    if position:
        price = df.iloc[-1]["close"]
        entry = position["entry"]
        qty = position["qty"]
        if position["side"] == "long":
            pnl = (price - entry) * qty * MAX_LEVERAGE
        else:
            pnl = (entry - price) * qty * MAX_LEVERAGE
        balance += pnl
        trades.append({
            "close_time": df.index[-1],
            "side": position["side"],
            "entry": entry,
            "exit": price,
            "size_usdt": position["size"],
            "pnl": pnl,
            "balance": balance,
        })

    # --- Results ---
    results = pd.DataFrame(trades)
    if results.empty:
        print("Keine Trades im gewählten Zeitraum.")
        return

    wins = results[results["pnl"] > 0]
    losses = results[results["pnl"] <= 0]
    total_pnl = results["pnl"].sum()
    winrate = len(wins) / len(results) * 100
    avg_win = wins["pnl"].mean() if not wins.empty else 0
    avg_loss = losses["pnl"].mean() if not losses.empty else 0
    best_trade = results["pnl"].max()
    worst_trade = results["pnl"].min()

    # Max Drawdown
    peak = results["balance"].cummax()
    drawdown = (results["balance"] - peak) / peak * 100
    max_drawdown = drawdown.min()

    print("\n" + "=" * 50)
    print(f"  BACKTEST: {symbol} | {timeframe} | {days} Tage")
    print(f"  ATR: {ATR_PERIOD} | Multiplier: {ATR_MULTIPLIER} | Hebel: {MAX_LEVERAGE}x")
    print("=" * 50)
    print(f"  Startkapital:      {capital:.2f} USDT")
    print(f"  Endkapital:        {balance:.2f} USDT")
    print(f"  Gesamt PnL:        {total_pnl:+.2f} USDT  ({total_pnl/capital*100:+.1f}%)")
    print(f"  Max Drawdown:      {max_drawdown:.1f}%")
    print("-" * 50)
    print(f"  Trades gesamt:     {len(results)}")
    print(f"  Gewinner:          {len(wins)}  ({winrate:.1f}%)")
    print(f"  Verlierer:         {len(losses)}")
    print(f"  Avg. Gewinn:       {avg_win:+.2f} USDT")
    print(f"  Avg. Verlust:      {avg_loss:+.2f} USDT")
    print(f"  Bester Trade:      {best_trade:+.2f} USDT")
    print(f"  Schlechtster:      {worst_trade:+.2f} USDT")
    print("=" * 50)

    print("\nLetzte 10 Trades:")
    print(results[["close_time", "side", "entry", "exit", "pnl", "balance"]].tail(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supertrend Backtest")
    parser.add_argument("--symbol", default="BTC/USDT", help="Trading Pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", default="15m", help="Zeitraum (default: 15m)")
    parser.add_argument("--days", type=int, default=90, help="Historische Tage (default: 90)")
    parser.add_argument("--capital", type=float, default=1000, help="Startkapital in USDT (default: 1000)")
    args = parser.parse_args()

    run_backtest(args.symbol, args.timeframe, args.days, args.capital)
