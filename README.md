# Automated Options Trading Engine

A production-oriented algorithmic trading framework built in Python for automated intraday options trading using Shoonya/Flattrade APIs. The system is designed to process live market data, execute trades automatically, monitor open positions in real time, and apply dynamic risk management for derivatives trading.

## Features

* Real-time market data streaming using WebSockets
* Automated order placement and execution
* VWAP and EMA based strategy logic
* Delta-based strike selection for options trading
* Option chain analytics and Greeks integration
* Position monitoring and MTM risk management
* Multi-threaded trade lifecycle automation
* Logging and session management utilities
* Support for NIFTY and BANKNIFTY derivatives trading

## Tech Stack

* Python
* Pandas
* WebSocket APIs
* REST APIs
* Shoonya / Flattrade APIs
* Quantitative Trading Concepts

## Project Structure

```text
config.py        -> Strategy and broker configuration
Utility.py       -> Helper functions and API utilities
finOrder.py      -> Order execution and management
NorenApi.py      -> Trading API integration layer
Logger.py        -> Logging and monitoring
init.py          -> Strategy initialization and execution logic
```

## Disclaimer

This project is intended for educational and research purposes only. It should not be considered financial advice or used directly for live trading without proper testing, validation, and risk controls.

## Author

SARVESHH-V

