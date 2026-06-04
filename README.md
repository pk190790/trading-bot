# Supertrend Trading Bot

Automatischer Trading Bot basierend auf dem **Supertrend Indicator** (ATR 10, Multiplier 3.0).
Holt Candlestick-Daten direkt von Binance Futures — kein TradingView Paid Plan nötig.

## Setup

```bash
# 1. Python Virtual Environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. API Keys konfigurieren
cp .env.example .env
# .env öffnen und Testnet API Keys eintragen
```

## Binance Futures Testnet API Keys

1. Gehe zu https://testnet.binancefuture.com
2. Login mit GitHub oder Google
3. Unter API Management → neuen Key erstellen
4. Key + Secret in `.env` eintragen

## Bot starten

```bash
source venv/bin/activate
python -m src.main
```

## Konfiguration (.env)

| Variable | Default | Beschreibung |
|---|---|---|
| `SYMBOL` | `BTC/USDT` | Trading Pair |
| `TIMEFRAME` | `15m` | Kerzen-Zeitraum |
| `MAX_LEVERAGE` | `5` | Maximaler Hebel |
| `MAX_TRADE_USDT` | `100` | Max. Betrag pro Trade |
| `ATR_PERIOD` | `10` | Supertrend ATR Periode |
| `ATR_MULTIPLIER` | `3.0` | Supertrend Multiplikator |
| `BINANCE_TESTNET` | `true` | Testnet verwenden |

## Logs

Trades werden in `logs/trades.log` gespeichert.

## Sicherheit

- **Testnet zuerst!** Mindestens 2 Wochen testen bevor echtes Kapital eingesetzt wird.
- `.env` niemals committen (steht in `.gitignore`)
- Testnet-Keys sind von echten Binance-Keys getrennt
