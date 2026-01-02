# BitShares Portfolio Valuation Tool

This tool automates the valuation of your BitShares Liquidity Pool (LP) holdings across multiple accounts and portfolios ("Core" and "Growth").

## Scope & Capabilities

The primary scope of this application is to provide a real-time, consolidated valuation of complex on-chain assets, specifically focusing on Liquidity Pools on the BitShares blockchain.

**Key Capabilities:**
*   **Asset Support:**
    *   **Stablecoins:** USDT, USDC, and other pegged assets.
    *   **Commodities:** Gold (XAUT), Silver, etc.
    *   **Cryptocurrencies:** RVN, EOS, TWENTIX, etc.
    *   **New Additions:** Recently added support for **USDT/USDC** stable pairs and **TWENTIX** specific pools in the Core portfolio.
*   **Valuation Logic:**
    *   **Stable Reference:** Uses "Stablecoin x 2" method for pools containing strictly stable assets.
    *   **Cross-Reference:** Uses "TWENTIX Reference Price" to triangulate value for volatile pairs.
*   **Tracking:** Monitors multiple user accounts simultaneously.

## Features

*   **Multi-Account Tracking:** Aggregates balances from multiple BitShares accounts.
*   **Dual Portfolios:** Separates assets into "Core" (Stable/USD-focused) and "Growth" (Speculative/Token-focused) categories.
*   **Data Persistence:** Saves history to CSV files (`capital_history_usd.csv` and `capital_history_growth.csv`).
*   **GUI:** Includes a graphical interface for easy viewing and historical charting.

## Setup

1.  **Install Python:** Ensure you have Python 3.x installed.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

*   **Accounts:** Managed in `user_settings.json`. Add or remove account IDs (e.g., `1.2.xxxxxx`) in the `accounts` list.
*   **Portfolios:**
    *   `config_core.json`: Configuration for Core assets (USD Stable Portfolio).
    *   `config_growth.json`: Configuration for Growth assets.

## Usage

### 1. Command Line Interface (CLI)
Run the script to generate CSV reports and see the output in the console:

```bash
python valuation.py
```

### 2. Graphical User Interface (GUI)
Launch the visual dashboard:

```bash
python gui_valuation.py
```
*   Click **"Refresh Data"** to fetch the latest data.
*   Switch tabs to view details for Core vs. Growth.

## Output Files
*   `capital_history_usd.csv`: Historical valuation data for the Core portfolio.
*   `capital_history_growth.csv`: Historical valuation data for the Growth portfolio.

## Technical Notes
*   `COMS.py` and `gui.py` are legacy tools for Credit Offer management and are not required for the valuation workflow.