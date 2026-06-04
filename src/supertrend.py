import pandas as pd


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Wilder's ATR — matches PineScript atr() function."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    # Wilder smoothing (RMA) — same as PineScript default atr()
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


def calculate_supertrend(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Replicates PineScript v4 Supertrend logic exactly.
    df must have columns: open, high, low, close, volume (lowercase)
    Returns df with added columns: supertrend_up, supertrend_dn, trend, buy_signal, sell_signal
    """
    df = df.copy()

    src = (df["high"] + df["low"]) / 2  # hl2

    atr = _atr(df, atr_period)

    raw_up = src - (multiplier * atr)
    raw_dn = src + (multiplier * atr)

    up = [0.0] * len(df)
    dn = [0.0] * len(df)
    trend = [1] * len(df)

    for i in range(len(df)):
        if i == 0:
            up[i] = raw_up.iloc[i]
            dn[i] = raw_dn.iloc[i]
            trend[i] = 1
            continue

        # Upper band (bullish support line)
        if df["close"].iloc[i - 1] > up[i - 1]:
            up[i] = max(raw_up.iloc[i], up[i - 1])
        else:
            up[i] = raw_up.iloc[i]

        # Lower band (bearish resistance line)
        if df["close"].iloc[i - 1] < dn[i - 1]:
            dn[i] = min(raw_dn.iloc[i], dn[i - 1])
        else:
            dn[i] = raw_dn.iloc[i]

        # Trend direction
        if trend[i - 1] == -1 and df["close"].iloc[i] > dn[i - 1]:
            trend[i] = 1
        elif trend[i - 1] == 1 and df["close"].iloc[i] < up[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    df["supertrend_up"] = up
    df["supertrend_dn"] = dn
    df["trend"] = trend
    df["buy_signal"] = (df["trend"] == 1) & (df["trend"].shift(1) == -1)
    df["sell_signal"] = (df["trend"] == -1) & (df["trend"].shift(1) == 1)

    return df


def get_latest_signal(df: pd.DataFrame):
    """Returns 'BUY', 'SELL', or None based on the last candle."""
    last = df.iloc[-1]
    if last["buy_signal"]:
        return "BUY"
    if last["sell_signal"]:
        return "SELL"
    return None
