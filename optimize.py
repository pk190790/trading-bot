"""
Supertrend Strategy Optimizer
Testet alle Kombinationen und gibt die beste Strategie aus.

Usage:
    python optimize.py
    python optimize.py --symbol ETH/USDT
    python optimize.py --days 180
"""

import argparse
import ccxt
import pandas as pd
import itertools
from src.supertrend import calculate_supertrend

# ── Parameter-Raster ──────────────────────────────────────────────────────────
ATR_PERIODS    = [7, 10, 14]
MULTIPLIERS    = [2.0, 3.0, 4.0]
TIMEFRAMES     = ["15m", "1h", "4h"]
LEVERAGES      = [1, 3, 5]
STOP_LOSSES    = [0, 1.5, 2.0, 3.0]   # % Verlust ab Entry (0 = kein SL)
MAX_TRADE_USDT = 100
CAPITAL        = 1000
FEE_RATE       = 0.0005  # 0.05% pro Trade (Binance Futures Taker)

def fetch_ohlcv(symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    exchange = ccxt.binanceusdm({
        "options": {"defaultType": "future", "fetchCurrencies": False},
    })
    exchange.urls["api"].update(exchange.urls["test"])
    tf_minutes = {"15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_minutes.get(timeframe, 15)
    limit = min(int(days * 24 * 60 / minutes), 1500)
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def backtest(df: pd.DataFrame, atr_period: int, multiplier: float, leverage: int, stop_loss_pct: float = 0) -> dict:
    df = calculate_supertrend(df.copy(), atr_period=atr_period, multiplier=multiplier)
    balance = CAPITAL
    position = None
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        price = row["close"]

        # Stop-Loss prüfen
        if position and stop_loss_pct > 0:
            entry = position["entry"]
            if position["side"] == "long":
                pnl_pct = (price - entry) / entry * 100
            else:
                pnl_pct = (entry - price) / entry * 100
            if pnl_pct <= -stop_loss_pct:
                qty = position["qty"]
                pnl = (price - entry) * qty * leverage if position["side"] == "long" \
                      else (entry - price) * qty * leverage
                fee = price * qty * FEE_RATE
                balance += pnl - fee
                trades.append(pnl - fee)
                position = None

        # Close on opposite signal
        if position:
            close = (row["buy_signal"] and position["side"] == "short") or \
                    (row["sell_signal"] and position["side"] == "long")
            if close:
                entry = position["entry"]
                qty = position["qty"]
                pnl = (price - entry) * qty * leverage if position["side"] == "long" \
                      else (entry - price) * qty * leverage
                fee = price * qty * FEE_RATE
                balance += pnl - fee
                trades.append(pnl - fee)
                position = None

        # Open new position
        if not position:
            if row["buy_signal"]:
                size = min(MAX_TRADE_USDT, balance * 0.1)
                fee = size * FEE_RATE
                balance -= fee
                position = {"side": "long",  "entry": price, "qty": size / price}
            elif row["sell_signal"]:
                size = min(MAX_TRADE_USDT, balance * 0.1)
                fee = size * FEE_RATE
                balance -= fee
                position = {"side": "short", "entry": price, "qty": size / price}

    # Close open position
    if position:
        price = df.iloc[-1]["close"]
        entry = position["entry"]
        qty = position["qty"]
        pnl = (price - entry) * qty * leverage if position["side"] == "long" \
              else (entry - price) * qty * leverage
        fee = price * qty * FEE_RATE
        balance += pnl - fee
        trades.append(pnl - fee)

    if not trades:
        return None

    s = pd.Series(trades)
    wins = s[s > 0]
    losses = s[s <= 0]

    # Running balance for drawdown
    running = CAPITAL
    peak = CAPITAL
    max_dd = 0.0
    for t in trades:
        running += t
        peak = max(peak, running)
        dd = (running - peak) / peak * 100
        max_dd = min(max_dd, dd)

    # Score = PnL% - abs(MaxDrawdown) * 0.5  (belohnt Gewinn, bestraft Risiko)
    pnl_pct = (balance - CAPITAL) / CAPITAL * 100
    score = pnl_pct - abs(max_dd) * 0.5

    return {
        "pnl_pct": round(pnl_pct, 2),
        "balance": round(balance, 2),
        "trades": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 1),
        "avg_win": round(wins.mean(), 2) if not wins.empty else 0,
        "avg_loss": round(losses.mean(), 2) if not losses.empty else 0,
        "max_drawdown": round(max_dd, 1),
        "score": round(score, 2),
    }


def run_optimizer(symbol: str, days: int) -> None:
    print(f"\nOptimiere {symbol} | {days} Tage | Kapital: {CAPITAL} USDT")
    total = len(ATR_PERIODS) * len(MULTIPLIERS) * len(TIMEFRAMES) * len(LEVERAGES) * len(STOP_LOSSES)
    print(f"Teste {total} Kombinationen...\n")

    # Cache OHLCV per timeframe
    cache = {}
    for tf in TIMEFRAMES:
        print(f"  Lade {tf} Daten...", end=" ", flush=True)
        cache[tf] = fetch_ohlcv(symbol, tf, days)
        print(f"{len(cache[tf])} Kerzen ✓")

    results = []
    combos = list(itertools.product(TIMEFRAMES, ATR_PERIODS, MULTIPLIERS, LEVERAGES, STOP_LOSSES))

    for tf, atr, mult, lev, sl in combos:
        r = backtest(cache[tf], atr, mult, lev, sl)
        if r:
            r.update({"timeframe": tf, "atr": atr, "multiplier": mult, "leverage": lev, "stop_loss": sl})
            results.append(r)

    df_res = pd.DataFrame(results).sort_values("score", ascending=False)

    # ── Top 10 ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print(f"  TOP 10 STRATEGIEN — {symbol} | {days} Tage")
    print("=" * 75)
    print(f"  {'#':<3} {'TF':<5} {'ATR':<5} {'Mult':<6} {'Lev':<5} {'SL':<6}"
          f"{'PnL%':<8} {'Winrate':<9} {'Drawdown':<10} {'Score'}")
    print("-" * 80)
    for i, row in df_res.head(10).iterrows():
        sl_str = f"{row['stop_loss']}%" if row['stop_loss'] > 0 else "kein"
        print(f"  {df_res.index.get_loc(i)+1:<3} "
              f"{row['timeframe']:<5} {row['atr']:<5} {row['multiplier']:<6} "
              f"{row['leverage']}x    "
              f"{sl_str:<6}"
              f"{row['pnl_pct']:>+6.1f}%  "
              f"{row['winrate']:>5.1f}%    "
              f"{row['max_drawdown']:>6.1f}%    "
              f"{row['score']:>+6.1f}")

    # ── Beste Strategie Detail ─────────────────────────────────────────────────
    best = df_res.iloc[0]
    print("\n" + "=" * 75)
    print("  🏆 BESTE STRATEGIE")
    print("=" * 75)
    print(f"  Timeframe:       {best['timeframe']}")
    print(f"  ATR Period:      {best['atr']}")
    print(f"  ATR Multiplier:  {best['multiplier']}")
    print(f"  Hebel:           {best['leverage']}x")
    sl_display = f"{best['stop_loss']}%" if best['stop_loss'] > 0 else "deaktiviert"
    print(f"  Stop-Loss:       {sl_display}")
    print(f"  PnL:             {best['pnl_pct']:+.1f}%  ({best['balance'] - CAPITAL:+.2f} USDT)")
    print(f"  Endkapital:      {best['balance']:.2f} USDT")
    print(f"  Trades:          {best['trades']}")
    print(f"  Winrate:         {best['winrate']}%")
    print(f"  Avg. Gewinn:     +{best['avg_win']:.2f} USDT")
    print(f"  Avg. Verlust:    {best['avg_loss']:.2f} USDT")
    print(f"  Max Drawdown:    {best['max_drawdown']}%")
    print("=" * 75)
    print(f"\n  → Trage in .env ein:")
    print(f"    TIMEFRAME={best['timeframe']}")
    print(f"    ATR_PERIOD={best['atr']}")
    print(f"    ATR_MULTIPLIER={best['multiplier']}")
    print(f"    MAX_LEVERAGE={best['leverage']}")
    if best['stop_loss'] > 0:
        print(f"    STOP_LOSS_PCT={best['stop_loss']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supertrend Optimizer")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    run_optimizer(args.symbol, args.days)
