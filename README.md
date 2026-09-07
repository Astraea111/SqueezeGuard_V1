## Squeeze Guard V2 — Agent OS workflow

Squeeze Guard V2 is a reusable AI workflow for analyzing
short-squeeze and long-squeeze pressure on Binance Futures.

The user runs SQUEEZE_GUARD_V2.md in ChatGPT with Binance
Agent OS connected. The agent retrieves market data, applies
explicit scoring rules, and explains the point breakdown.

### How to run

1. Connect Binance Agent OS in ChatGPT.
2. Copy the instructions from SQUEEZE_GUARD_V2.md.
3. Send the instructions to the connected chat.
4. Review the tool calls, timestamps, two pressure scores,
   component breakdown, and missing-data notices.

The scores are experimental heuristic indices, not
probabilities or validated predictions. Missing inputs
produce an incomplete score rather than fabricated values.

Market-data only. No account access or transactions.

### Earlier dashboard prototype

app.py is the earlier V1 Streamlit dashboard.
It uses Binance REST API and a different five-component
scoring model. It does not implement the V2 agent workflow.

### Demo
# Squeeze Guard

Squeeze Guard is a dashboard prototype for monitoring market conditions in Binance USDT perpetual futures. The dashboard displays market data and two rule-based indices: **short-pressure** and **long-pressure**. Individual score components can be inspected, and the resulting JSON report can be verified via the Binance Agent OS in ChatGPT.

## Workflow

1. The user retrieves public Binance data through the Streamlit dashboard.
2. Python validates the data timestamp and calculates indicators and scores.
3. The user downloads the JSON report and uploads it to ChatGPT.
4. ChatGPT uses the available Binance Agent OS connection to check the data from the report's timestamp and explain the results.

Report transfer is performed manually; the dashboard is not yet automatically connected to the AI ​​model or MCP. The interface name "Squeeze Guard AI" refers to the project itself, while the dashboard's calculations rely on Python rules.

## Current features

- Selection of BTCUSDT, ETHUSDT, BNBUSDT, and SOLUSDT.
- Last price, price change, and 24-hour USDT volume.
- Closing price line chart and 15-minute OHLC candle table.
- 1-hour return and relative volume (RVOL) based on closed candles.
- Funding and open interest (OI) history.
- Scores with a breakdown of points per component and data timestamp.
- JSON export and data retrieval success logs.

Updates are triggered using the **Fetch full data** button. Request caching lasts for a maximum of 30 seconds; data does not update automatically.

## Project files

| File | Function |
|---|---|
| `app.py` | Dashboard and indicator calculations |
| `SQUEEZE_GUARD_INSTRUCTIONS.md` | Instructions for report verification via ChatGPT and Binance Agent OS |
| `README.md` | This guide |
| `squeeze_guard_BTCUSDT.json` | Example filename for reports downloaded from the dashboard |

## Running on Windows

Prerequisites: Python (accessible via the `py` command), an internet connection, and the project files located in a single folder. This project has been successfully run using Python 3.14.7. ### Initial installation

Open the SqueezeGuard folder in File Explorer. Click the address bar, type `cmd`, and press Enter. Run the following commands one by one:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install streamlit pandas requests
.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically. Keep the CMD window open while using the application.

### Relaunching

If dependencies are already installed, open CMD from the project folder and run:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

There is no need to reinstall Python each time you open the application. To stop the server, press Ctrl+C in the CMD window.

## Using the dashboard and Agent OS

1. Select a pair, e.g., BTCUSDT.
2. Click **Fetch complete data** and wait for the process to finish.
3. Check the data timestamp, indicators, and score table.
4. Click **Download JSON report**.
5. Upload the JSON to a ChatGPT instance connected to Binance Agent OS. Include the instructions from `SQUEEZE_GUARD_INSTRUCTIONS.md`.
6. Request a check for the same report timestamp. Distinguish between data that matches, differs, or cannot yet be verified.

Example message:

> Check this JSON report following SQUEEZE_GUARD_INSTRUCTIONS.md. Use Binance Agent OS to verify the candle at `candle_oi_boundary_utc`. Display the last close price, the highest high from the previous 20 candles, the breakout result, and the data timestamp. Do not access balances or execute transactions. If the tool fails, explain the failure without fabricating data.

This workflow does not require purchasing model API credits for the dashboard. Usage of ChatGPT and the Agent OS connection is subject to the user account's access rights and usage limits.

## Data and calculations

The dashboard uses the public API at `https://fapi.binance.com`:

| Endpoint | Usage |
|---|---|
| `/fapi/v1/time` | Server time |
| `/fapi/v1/ticker/24hr` | 24-hour price and volume summary |
| `/fapi/v1/klines` | 60 candles, 15-minute interval |
| `/fapi/v1/premiumIndex` | `lastFundingRate` reading and funding time |
| `/futures/data/openInterestHist` | 8 OI data points, 15-minute interval |

The current (incomplete) candle is excluded from calculations. For the score, the application selects the latest available timestamp from the candles and OI data, up to a maximum of 30 minutes prior to the snapshot server time. Dashboard indicators at the top may utilize data that is more recent than the score itself.

- **1H Return:** `(latest close / close from four intervals ago − 1) × 100`.
- **RVOL:** Quote volume of the latest candle divided by the average quote volume of the preceding 20 candles.
- **1H OI Change:** `(sumOpenInterest at timestamp / sumOpenInterest one hour prior − 1) × 100`.
- **Breakout:** Latest close is higher than the highest high of the preceding 20 candles.
- **Breakdown:** Latest close is lower than the lowest low of the preceding 20 candles.

The latest candle is excluded from the set of 20 comparison candles. A close equal to the comparison high/low does not qualify as a breakout/breakdown. OI uses base asset units, not dollar value. Funding uses the latest reading.
Video link will be added after recording.

