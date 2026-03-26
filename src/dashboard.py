import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="S&P 500 Pipeline Dashboard", layout="wide")


@st.cache_data
def load_stocks():
    df = pd.read_csv("data/sp500_stocks.csv")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.dropna(subset=["close"])
    df["date"] = pd.to_datetime(df["date"])
    df["daily_return_pct"] = ((df["close"] - df["open"]) / df["open"] * 100).round(4)
    return df


@st.cache_data
def load_companies():
    df = pd.read_csv("data/sp500_companies.csv")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


@st.cache_data
def load_index():
    df = pd.read_csv("data/sp500_index.csv")
    df.columns = [c.strip().lower().replace(" ", "_").replace("&", "").replace("s_p500", "sp500") for c in df.columns]
    # Handle column name: "S&P500" -> "s&p500" -> "sp500" after cleanup
    df = df.rename(columns={c: "sp500" for c in df.columns if "p500" in c.lower()})
    df["date"] = pd.to_datetime(df["date"])
    return df


stocks = load_stocks()
companies = load_companies()
index = load_index()

# Merge sector info
stocks_with_sector = stocks.merge(
    companies[["symbol", "sector", "industry", "longname"]], on="symbol", how="left"
)

# ---- Header ----
st.title("S&P 500 Data Pipeline Dashboard")
st.markdown("Real-time analytics from the Kafka-Spark-S3 pipeline")

# ---- KPI Row ----
col1, col2, col3, col4 = st.columns(4)
latest_date = stocks["date"].max()
latest_day = stocks[stocks["date"] == latest_date]

col1.metric("Trading Days", f"{stocks['date'].nunique():,}")
col2.metric("Stocks Tracked", f"{stocks['symbol'].nunique()}")
col3.metric("Total Records", f"{len(stocks):,}")
col4.metric("Latest Date", latest_date.strftime("%Y-%m-%d"))

st.divider()

# ---- Sidebar Filters ----
st.sidebar.header("Filters")

sectors = sorted(stocks_with_sector["sector"].dropna().unique())
selected_sectors = st.sidebar.multiselect("Sector", sectors, default=sectors)

date_range = st.sidebar.date_input(
    "Date Range",
    value=(stocks["date"].min(), stocks["date"].max()),
    min_value=stocks["date"].min(),
    max_value=stocks["date"].max(),
)

# Apply filters
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
    end_date = stocks["date"].max()

mask = (
    stocks_with_sector["sector"].isin(selected_sectors)
    & (stocks_with_sector["date"] >= pd.Timestamp(start_date))
    & (stocks_with_sector["date"] <= pd.Timestamp(end_date))
)
filtered = stocks_with_sector[mask]

# ---- Tab Layout ----
tab1, tab2, tab3, tab4 = st.tabs(["Price Trends", "Sector Analysis", "Top Movers", "Index Correlation"])

# ---- Tab 1: Price Trends ----
with tab1:
    st.subheader("Stock Price Over Time")

    popular = ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "TSLA"]
    available = [s for s in popular if s in filtered["symbol"].unique()]
    selected_stocks = st.multiselect("Select stocks", sorted(filtered["symbol"].unique()), default=available[:5])

    if selected_stocks:
        price_data = filtered[filtered["symbol"].isin(selected_stocks)]
        fig = px.line(
            price_data,
            x="date",
            y="close",
            color="symbol",
            title="Closing Price",
            labels={"close": "Close Price ($)", "date": "Date"},
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

        # Volume chart
        fig_vol = px.bar(
            price_data.groupby(["date", "symbol"])["volume"].sum().reset_index(),
            x="date",
            y="volume",
            color="symbol",
            title="Trading Volume",
            labels={"volume": "Volume", "date": "Date"},
        )
        st.plotly_chart(fig_vol, width="stretch")

# ---- Tab 2: Sector Analysis ----
with tab2:
    st.subheader("Performance by Sector")

    col_a, col_b = st.columns(2)

    with col_a:
        # Sector market cap distribution
        sector_mcap = companies.groupby("sector")["marketcap"].sum().reset_index()
        sector_mcap["marketcap_b"] = (sector_mcap["marketcap"] / 1e9).round(1)
        fig_mc = px.pie(
            sector_mcap,
            values="marketcap_b",
            names="sector",
            title="Market Cap by Sector ($B)",
        )
        st.plotly_chart(fig_mc, width="stretch")

    with col_b:
        # Average daily return by sector
        sector_return = (
            filtered.groupby("sector")["daily_return_pct"]
            .mean()
            .reset_index()
            .sort_values("daily_return_pct", ascending=True)
        )
        fig_sr = px.bar(
            sector_return,
            x="daily_return_pct",
            y="sector",
            orientation="h",
            title="Avg Daily Return by Sector (%)",
            labels={"daily_return_pct": "Avg Return %", "sector": ""},
            color="daily_return_pct",
            color_continuous_scale="RdYlGn",
        )
        st.plotly_chart(fig_sr, width="stretch")

    # Sector volume over time
    sector_vol = (
        filtered.groupby(["date", "sector"])["volume"]
        .sum()
        .reset_index()
    )
    fig_sv = px.area(
        sector_vol,
        x="date",
        y="volume",
        color="sector",
        title="Trading Volume by Sector Over Time",
    )
    st.plotly_chart(fig_sv, width="stretch")

# ---- Tab 3: Top Movers ----
with tab3:
    st.subheader("Top Daily Movers")

    selected_date = st.date_input(
        "Select a trading date",
        value=latest_date,
        min_value=stocks["date"].min(),
        max_value=stocks["date"].max(),
    )

    day_df = filtered[filtered["date"] == pd.Timestamp(selected_date)].copy()

    if len(day_df) == 0:
        st.warning("No data for this date. Try a trading day.")
    else:
        day_df["abs_return"] = day_df["daily_return_pct"].abs()
        top_n = st.slider("Number of movers", 5, 30, 10)

        col_g, col_l = st.columns(2)

        with col_g:
            gainers = day_df.nlargest(top_n, "daily_return_pct")
            fig_gain = px.bar(
                gainers,
                x="daily_return_pct",
                y="symbol",
                orientation="h",
                title=f"Top {top_n} Gainers",
                color="daily_return_pct",
                color_continuous_scale="Greens",
                labels={"daily_return_pct": "Return %", "symbol": ""},
            )
            st.plotly_chart(fig_gain, width="stretch")

        with col_l:
            losers = day_df.nsmallest(top_n, "daily_return_pct")
            fig_lose = px.bar(
                losers,
                x="daily_return_pct",
                y="symbol",
                orientation="h",
                title=f"Top {top_n} Losers",
                color="daily_return_pct",
                color_continuous_scale="Reds_r",
                labels={"daily_return_pct": "Return %", "symbol": ""},
            )
            st.plotly_chart(fig_lose, width="stretch")

        # Day summary table
        st.dataframe(
            day_df[["symbol", "longname", "sector", "open", "close", "high", "low", "volume", "daily_return_pct"]]
            .sort_values("daily_return_pct", ascending=False, key=abs)
            .head(50)
            .reset_index(drop=True),
            width="stretch",
        )

# ---- Tab 4: Index Correlation ----
with tab4:
    st.subheader("Stock vs S&P 500 Index")

    stock_pick = st.selectbox("Select a stock", sorted(filtered["symbol"].unique()), index=0)

    stock_ts = filtered[filtered["symbol"] == stock_pick][["date", "close"]].set_index("date")
    index_ts = index.set_index("date")[["sp500"]]

    merged = stock_ts.join(index_ts, how="inner")

    if len(merged) > 0:
        # Normalize to 100 for comparison
        merged_norm = merged.copy()
        merged_norm["close"] = merged_norm["close"] / merged_norm["close"].iloc[0] * 100
        merged_norm["sp500"] = merged_norm["sp500"] / merged_norm["sp500"].iloc[0] * 100

        fig_corr = go.Figure()
        fig_corr.add_trace(go.Scatter(x=merged_norm.index, y=merged_norm["close"], name=stock_pick, mode="lines"))
        fig_corr.add_trace(go.Scatter(x=merged_norm.index, y=merged_norm["sp500"], name="S&P 500", mode="lines"))
        fig_corr.update_layout(
            title=f"{stock_pick} vs S&P 500 (Normalized to 100)",
            yaxis_title="Normalized Price",
            hovermode="x unified",
        )
        st.plotly_chart(fig_corr, width="stretch")

        corr_val = merged["close"].corr(merged["sp500"])
        st.metric("Pearson Correlation", f"{corr_val:.4f}")

        # Scatter plot
        fig_scatter = px.scatter(
            merged.reset_index(),
            x="sp500",
            y="close",
            trendline="ols",
            title=f"{stock_pick} Close vs S&P 500 Index",
            labels={"sp500": "S&P 500", "close": f"{stock_pick} Close ($)"},
        )
        st.plotly_chart(fig_scatter, width="stretch")
    else:
        st.warning("No overlapping dates between stock and index data.")
