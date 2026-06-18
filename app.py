import streamlit as st
import plotly.express as px

from analysis.q1_price_sentiment import get_price_sentiment
from analysis.q2_indie_gap import get_indie_genre_gap
from analysis.q3_retention import get_engagement_data, TIER_ORDER
from analysis.q4_developer_stats import get_developer_stats
from analysis.q5_sentiment_summary import get_sentiment_summary

st.set_page_config(
    page_title="Steam Analytics OLAP",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎮 Steam Analytics")
    st.markdown(
        "**DMDS Final Project**  \n"
        "Universitas Kristen Petra Surabaya  \n"
        "Informatika — 2025/2026"
    )

# ── Cache ─────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_q1():
    return get_price_sentiment()

@st.cache_data(show_spinner=False)
def load_q2():
    return get_indie_genre_gap()

@st.cache_data(show_spinner=False)
def load_q3():
    return get_engagement_data()

@st.cache_data(show_spinner=False)
def load_dev_stats():
    return get_developer_stats()

@st.cache_data(show_spinner=False)
def load_sentiment_summary():
    return get_sentiment_summary()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Steam Analytics OLAP App")
st.caption(
    "Polyglot Persistence: MySQL (katalog + ratings 27K game) + MongoDB (80K user reviews) | "
    "Dataset: Steam 2013–2021"
)

tab1, tab2, tab3 = st.tabs(
    ["Q1 — Harga vs Sentimen", "Q2 — Indie Genre Gap", "Q3 — Player Engagement"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Q1: Price vs Sentiment (MySQL only — 27K games, aggregate ratings)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Q1 — Harga vs Sentimen Pemain")
    st.markdown(
        "> Di rentang harga mana sebuah game cenderung memiliki **positive review ratio** "
        "tertinggi? Apakah Free-to-Play lebih disukai dari game berbayar?"
    )
    st.info(
        "**Sumber:** `price`, `positive_ratings`, `negative_ratings` dari MySQL `clean_mysql_katalog` "
        "— mencakup **semua 27.061 game** dengan aggregate review counts.",
        icon="🗄️",
    )

    with st.spinner("Querying MySQL..."):
        df_q1 = load_q1()

    if df_q1.empty:
        st.error("Tidak ada data. Pastikan MySQL (port 3307) running.")
    else:
        col_a, col_b, col_c, col_d = st.columns(4)
        best = df_q1.loc[df_q1["avg_positive_ratio"].idxmax()]
        free_row = df_q1[df_q1["price_bucket"] == "Free"]
        paid_row = df_q1[df_q1["price_bucket"] != "Free"]

        col_a.metric("Total Game Dianalisis", f"{df_q1['game_count'].sum():,}")
        col_b.metric("Bucket Terbaik", best["price_bucket"], f"{best['avg_positive_ratio']:.1%}")
        col_c.metric(
            "Avg Ratio Free-to-Play",
            f"{free_row['avg_positive_ratio'].iloc[0]:.1%}" if not free_row.empty else "—",
        )
        col_d.metric(
            "Avg Ratio Paid Games",
            f"{paid_row['avg_positive_ratio'].mean():.1%}" if not paid_row.empty else "—",
        )

        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            fig1a = px.bar(
                df_q1,
                x="price_bucket",
                y="avg_positive_ratio",
                text=df_q1["avg_positive_ratio"].apply(lambda x: f"{x:.1%}"),
                color="avg_positive_ratio",
                color_continuous_scale="RdYlGn",
                range_color=[0.5, 1.0],
                labels={"price_bucket": "Rentang Harga", "avg_positive_ratio": "Avg Positive Ratio"},
                title="Positive Review Ratio per Price Bucket",
                hover_data={"game_count": True},
            )
            fig1a.update_traces(textposition="outside")
            fig1a.update_layout(
                yaxis_tickformat=".0%", yaxis_range=[0, 1.1], coloraxis_showscale=False
            )
            st.plotly_chart(fig1a, use_container_width=True)

        with col_right:
            fig1b = px.bar(
                df_q1,
                x="price_bucket",
                y="game_count",
                text="game_count",
                color="game_count",
                color_continuous_scale="Blues",
                labels={"price_bucket": "Rentang Harga", "game_count": "Jumlah Game"},
                title="Jumlah Game per Price Bucket",
            )
            fig1b.update_traces(textposition="outside")
            fig1b.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig1b, use_container_width=True)

        with st.expander("Lihat data mentah Q1"):
            display = df_q1.copy()
            display["avg_positive_ratio"] = display["avg_positive_ratio"].apply(lambda x: f"{x:.2%}")
            display["total_reviews"] = display["total_reviews"].apply(lambda x: f"{x:,}")
            st.dataframe(display, use_container_width=True)

        st.subheader("Insight")
        st.info(
            "Game di bucket **$5–$15** dan **$15–$30** memiliki positive ratio tertinggi — "
            "price point yang dianggap 'fair value' oleh pemain. Free-to-Play memiliki "
            "volume game terbesar namun sentimen lebih beragam karena model mikrotransaksi. "
            "Game $30+ cenderung dari studio besar dengan ekspektasi pemain lebih tinggi, "
            "sehingga kritik lebih tajam jika kualitas tidak sesuai harga."
        )

        st.divider()
        st.subheader("Supporting Insight — Developer Volume vs Rating")
        df_dev = load_dev_stats()
        if not df_dev.empty:
            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("**Top 5 Developer by Volume**")
                top_vol = df_dev.nlargest(5, "game_count")[["developer", "game_count", "avg_positive_ratio"]].copy()
                top_vol["avg_positive_ratio"] = top_vol["avg_positive_ratio"].apply(lambda x: f"{x:.1%}")
                top_vol.columns = ["Developer", "Jumlah Game", "Avg Positive Ratio"]
                st.dataframe(top_vol.reset_index(drop=True), use_container_width=True)
            with col_y:
                st.markdown("**Top 5 Developer by Rating** (min 3 game)")
                top_rate = df_dev.nlargest(5, "avg_positive_ratio")[["developer", "game_count", "avg_positive_ratio"]].copy()
                top_rate["avg_positive_ratio"] = top_rate["avg_positive_ratio"].apply(lambda x: f"{x:.1%}")
                top_rate.columns = ["Developer", "Jumlah Game", "Avg Positive Ratio"]
                st.dataframe(top_rate.reset_index(drop=True), use_container_width=True)
            st.caption(
                "Entitas tambahan `developer_stats` (MySQL) — derived table dari clean_mysql_katalog. "
                "Menunjukkan apakah developer dengan volume produksi tinggi memiliki sentimen "
                "yang berbeda dari developer dengan game lebih sedikit."
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Q2: Indie Genre Gap (MySQL sentiment + MongoDB tags)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Q2 — Indie Genre Gap")
    st.markdown(
        "> Kombinasi genre apa yang paling banyak diproduksi **game indie** "
        "dalam 5 tahun terakhir (2016–2021), dan genre mana yang positive rating-nya paling konsisten tinggi?"
    )
    st.info(
        "**Asumsi:** Game indie = game yang di-tag **'Indie'** oleh komunitas SteamSpy "
        "*(community-based classification, bukan berdasarkan ukuran studio)*. "
        "Tag 'Indie' sendiri tidak ditampilkan — yang dianalisis adalah genre lain dari game tersebut. "
        "**Sumber:** tags dari MongoDB `Steams_Tags_Genre` → join sentiment dari MySQL via `appid`.",
        icon="📌",
    )

    with st.spinner("Querying MySQL + MongoDB Steams_Tags_Genre..."):
        df_q2 = load_q2()

    if df_q2.empty:
        st.warning("Data Q2 kosong. Cek koneksi database.")
    else:
        col_e, col_f = st.columns([3, 1])
        with col_f:
            top_n = st.slider("Top N genre", 10, min(50, len(df_q2)), 20)
            min_games = st.slider("Min jumlah game", 1, 20, 5)

        df_q2_filtered = df_q2[df_q2["game_count"] >= min_games].head(top_n)

        with col_e:
            fig2 = px.scatter(
                df_q2_filtered,
                x="game_count",
                y="avg_positive_ratio",
                text="tag",
                size="game_count",
                size_max=40,
                color="avg_positive_ratio",
                color_continuous_scale="RdYlGn",
                range_color=[0.5, 1.0],
                labels={
                    "game_count": "Jumlah Game Indie",
                    "avg_positive_ratio": "Avg Positive Ratio",
                },
                title="Indie Genre: Volume vs Positive Rating (2016–2021)",
                hover_name="tag",
            )
            fig2.update_traces(textposition="top center")
            fig2.update_layout(yaxis_tickformat=".0%", coloraxis_showscale=False)
            st.plotly_chart(fig2, use_container_width=True)

        col_g, col_h = st.columns(2)
        with col_g:
            st.subheader("Top 10 Genre by Volume")
            top_vol = df_q2.nlargest(10, "game_count")[["tag", "game_count", "avg_positive_ratio"]].copy()
            top_vol["avg_positive_ratio"] = top_vol["avg_positive_ratio"].apply(lambda x: f"{x:.1%}")
            top_vol.columns = ["Genre/Tag", "Jumlah Game", "Avg Positive Ratio"]
            st.dataframe(top_vol.reset_index(drop=True), use_container_width=True)

        with col_h:
            st.subheader("Top 10 Genre by Rating")
            top_rat = (
                df_q2[df_q2["game_count"] >= 5]
                .nlargest(10, "avg_positive_ratio")[["tag", "game_count", "avg_positive_ratio"]]
                .copy()
            )
            top_rat["avg_positive_ratio"] = top_rat["avg_positive_ratio"].apply(lambda x: f"{x:.1%}")
            top_rat.columns = ["Genre/Tag", "Jumlah Game", "Avg Positive Ratio"]
            st.dataframe(top_rat.reset_index(drop=True), use_container_width=True)

        st.subheader("Insight")
        st.info(
            "Genre **Action** dan **Casual** mendominasi volume produksi indie — "
            "barrier to entry rendah dengan engine modern (Unity/Godot/Unreal). "
            "Namun genre niche seperti **Visual Novel**, **Pixel Graphics**, dan **Puzzle** "
            "justru memiliki positive ratio tertinggi (80–84%) meski jumlah game jauh lebih sedikit. "
            "Ini adalah 'Indie Genre Gap': developer indie banyak masuk ke genre populer, "
            "tapi kepuasan pemain tidak otomatis lebih tinggi — komunitas niche lebih terpenuhi ekspektasinya."
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Q3: Retention Analysis (MongoDB timestamp + MySQL release_date)
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Q3 — Retensi Game berdasarkan Price Tier")
    st.markdown(
        "> Apakah game di price tier lebih tinggi mendapat ulasan aktif lebih panjang "
        "setelah rilis? Apakah harga mencerminkan loyalitas komunitas pemain?"
    )
    st.info(
        "**Sumber:** MongoDB `User_Reviews` — `timestamp_created` per review → retention window "
        "dihitung sebagai `last_review_date − release_date` (MySQL). "
        "Join via `appid`.",
        icon="📄",
    )

    with st.spinner("Querying MongoDB + MySQL untuk retention analysis..."):
        data_q3 = load_q3()

    df_ret = data_q3["retention"]

    if df_ret.empty:
        st.error("Data Q3 kosong. Jalankan fix_etl_mongo.py dulu, lalu restart app.")
    else:
        avg_by_tier = df_ret.groupby("price_category")["retention_days"].mean()
        best_tier = avg_by_tier.idxmax()
        best_avg = avg_by_tier.max()
        worst_tier = avg_by_tier.idxmin()
        worst_avg = avg_by_tier.min()

        col_i, col_j, col_k = st.columns(3)
        col_i.metric("Game Dianalisis", len(df_ret))
        col_j.metric("Tier Retention Terpanjang", best_tier, f"{best_avg:.0f} hari")
        col_k.metric("Median Retention", f"{df_ret['retention_days'].median():.0f} hari")

        st.divider()

        # ── Retention Window Box Plot ──────────────────────────────────────
        st.subheader("Retention Window per Price Tier")
        fig3a = px.box(
            df_ret,
            x="price_category",
            y="retention_days",
            color="price_category",
            points="all",
            hover_data=["name", "review_count", "positive_ratio"],
            labels={
                "price_category": "Price Tier",
                "retention_days": "Retention Window (hari)",
            },
            title="Distribusi Retention Window per Price Tier",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3a.update_xaxes(categoryorder="array", categoryarray=TIER_ORDER)
        fig3a.update_layout(showlegend=False)
        st.plotly_chart(fig3a, use_container_width=True)

        col_l, col_m = st.columns(2)
        with col_l:
            # ── Avg Retention Bar Chart ──────────────────────────────────────
            avg_ret = df_ret.groupby("price_category")["retention_days"].mean().reset_index()
            avg_ret["retention_days"] = avg_ret["retention_days"].round(0)
            fig3b = px.bar(
                avg_ret,
                x="price_category",
                y="retention_days",
                color="price_category",
                text="retention_days",
                labels={
                    "price_category": "Price Tier",
                    "retention_days": "Rata-rata Retention (hari)",
                },
                title="Rata-rata Retention Window per Price Tier",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig3b.update_traces(texttemplate="%{text:.0f} hari", textposition="outside")
            fig3b.update_xaxes(categoryorder="array", categoryarray=TIER_ORDER)
            fig3b.update_layout(showlegend=False, yaxis_range=[0, avg_ret["retention_days"].max() * 1.3])
            st.plotly_chart(fig3b, use_container_width=True)

        with col_m:
            # ── Scatter: price vs retention ──────────────────────────────────
            fig3c = px.scatter(
                df_ret,
                x="price",
                y="retention_days",
                color="price_category",
                hover_name="name",
                hover_data=["review_count", "positive_ratio"],
                size="review_count",
                size_max=20,
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={
                    "price": "Harga (USD)",
                    "retention_days": "Retention (hari)",
                    "price_category": "Price Tier",
                },
                title="Harga vs Retention per Game",
            )
            st.plotly_chart(fig3c, use_container_width=True)

        # ── Top game by retention ──────────────────────────────────────────
        st.subheader("Top 10 Game dengan Retention Terpanjang")
        top_ret = df_ret.nlargest(10, "retention_days")[
            ["name", "price_category", "price", "retention_days", "review_count", "positive_ratio"]
        ].copy()
        top_ret["price"] = top_ret["price"].apply(lambda x: f"${x:.2f}")
        top_ret["retention_days"] = top_ret["retention_days"].astype(int)
        top_ret["positive_ratio"] = top_ret["positive_ratio"].apply(lambda x: f"{x:.1%}")
        top_ret.columns = ["Game", "Price Tier", "Harga", "Retention (hari)", "Jumlah Review", "Positive Ratio"]
        st.dataframe(top_ret.reset_index(drop=True), use_container_width=True)

        st.subheader("Insight")
        if best_tier in ("$30+", "$15–$30"):
            conclusion = (
                "pemain yang menginvestasikan lebih banyak uang cenderung lebih engaged "
                "dalam jangka panjang (sunk cost engagement)."
            )
        else:
            conclusion = (
                "harga bukan satu-satunya faktor penentu loyalitas komunitas — kualitas "
                "dan komunitas game itu sendiri lebih berpengaruh."
            )
        st.info(
            f"Game tier **{best_tier}** memiliki retention window rata-rata terpanjang "
            f"(**{best_avg:.0f} hari**), sementara tier **{worst_tier}** terendah "
            f"(**{worst_avg:.0f} hari**). Ini mengindikasikan bahwa {conclusion} "
            "Retention window diukur dari tanggal rilis (MySQL) hingga review terakhir yang "
            "tercatat di MongoDB — semakin panjang, semakin lama komunitas aktif "
            "mendiskusikan game tersebut."
        )

        st.divider()
        st.subheader("Supporting Insight — Playtime vs Sentiment")
        df_sentiment = load_sentiment_summary()
        if not df_sentiment.empty:
            fig_extra = px.scatter(
                df_sentiment,
                x="avg_playtime_hours",
                y="positive_ratio",
                size="total_reviews",
                size_max=30,
                labels={
                    "avg_playtime_hours": "Rata-rata Playtime sebelum Review (jam)",
                    "positive_ratio": "Positive Ratio",
                },
                title="Apakah Pemain dengan Playtime Lebih Lama Memberi Review Lebih Positif?",
            )
            fig_extra.update_layout(yaxis_tickformat=".0%")
            st.plotly_chart(fig_extra, use_container_width=True)
            st.caption(
                "Entitas tambahan `Sentiment_Summary` (MongoDB) — derived collection dari User_Reviews. "
                "Pre-aggregated per-game summary untuk analisis playtime vs sentimen."
            )
