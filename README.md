# ETHWatch — Ethereum On-chain Anomaly Detection

A production-ready pipeline for monitoring the Ethereum blockchain in real-time, detecting anomalous transactions, and visualizing them on a Streamlit dashboard.

## Overview

This project consists of two main components:
1. **Monitor (`monitor.py`)**: Continuously connects to an Ethereum node, downloads the latest blocks, and runs all transactions through an anomaly detection engine. Results are saved to a **PostgreSQL** database.
2. **Dashboard (`app.py`)**: A Streamlit web application that visually displays real-time statistics and recent anomalous transactions read from the shared database.

### Anomalies Detected
- **High Value Transfers**: Transactions moving unusually large amounts of ETH.
- **High Gas Prices**: Transactions paying extremely high gas prices (MEV bots or priority fee spikes).
- **Suspicious Contract Interactions**: Zero-value transfers with massive gas limits (flash loans or exploits).

## Project Structure

```
├── app.py              # Streamlit Dashboard UI
├── database.py         # PostgreSQL Database connection and schema
├── detector.py         # Anomaly detection logic
├── monitor.py          # Block scanner that feeds the database
├── requirements.txt    # Python dependencies
├── render.yaml         # Render.com Blueprint for monitor deployment
├── .env.example        # Example environment configuration
└── docker-compose.yml  # (Legacy) Local Docker setup
```

---

## Setup & Running

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ETH_RPC_URL` | Ethereum RPC URL (Alchemy/Infura recommended) |
| `DATABASE_URL` | PostgreSQL connection string (see Supabase below) |
| `HIGH_VALUE_THRESHOLD` | ETH value above which a tx is flagged (default: 10) |
| `HIGH_GAS_PRICE_THRESHOLD` | Gas price (Gwei) above which a tx is flagged (default: 100) |

### 2. Setting up the Database (Supabase — Free)

1. Go to [https://supabase.com](https://supabase.com) and create a free account.
2. Create a new project.
3. Go to **Settings → Database → Connection String → URI**.
4. Copy the connection string and paste it as `DATABASE_URL` in your `.env` file.

> The table schema is created automatically when you run `monitor.py` or `database.py` for the first time.

### 3. Running Locally

```bash
pip install -r requirements.txt

# Terminal 1 — Start the monitor
python monitor.py

# Terminal 2 — Start the dashboard
streamlit run app.py
```

---

## Cloud Deployment (Production)

### Deploy the Dashboard → Streamlit Community Cloud

1. Push the project to a **public or private GitHub repository**.
2. Go to [https://share.streamlit.io](https://share.streamlit.io) and connect your repository.
3. Set **Main file path** to `app.py`.
4. Add your secrets under **Advanced Settings**:
   ```toml
   DATABASE_URL = "postgresql://..."
   ETH_RPC_URL  = "https://..."
   ```
5. Click **Deploy**.

### Deploy the Monitor → Render Background Worker

1. Go to [https://render.com](https://render.com) and create an account.
2. Click **New → Blueprint** and connect your GitHub repository.
3. Render will automatically detect the `render.yaml` file and configure the background worker.
4. Add the following environment variables in the Render dashboard:
   - `ETH_RPC_URL` — your Alchemy or Infura endpoint
   - `DATABASE_URL` — your Supabase connection string
5. Click **Deploy** — the monitor will now run 24/7, writing to the shared PostgreSQL database.

> **Architecture:** Both the Streamlit Cloud dashboard and the Render worker connect to the same Supabase PostgreSQL database, so anomalies found by the monitor appear on the dashboard in real-time.

---

## Customizing Detection Rules

Modify `detector.py` to add new anomaly types:
1. Add a new `_assess_...` function returning `{"type", "severity", "description"}`.
2. Call it from the `analyze_transaction` method.
