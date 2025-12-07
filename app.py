import json
import math
import gzip
import streamlit as st
import pandas as pd

# --------------------------------------------------------------
# 🧭 Streamlit Configuration
# --------------------------------------------------------------
# Set page title and use wide layout for better table display.
st.set_page_config(page_title="Data Lowongan Magang", layout="wide")

# --------------------------------------------------------------
# 🏷️ Page Header
# --------------------------------------------------------------
st.title("📊 Data Lowongan Magang - KEMNAKER")
st.markdown(
    """
    Menampilkan data hasil scraping lowongan magang aktif dari
    [maganghub.kemnaker.go.id](https://maganghub.kemnaker.go.id)
    """
)
st.markdown(
    """
    ```
    Data terakhir diperbarui pada: 2025-12-07 14:15 WIB
    ```
    """, width= 'content'
)


# --------------------------------------------------------------
# 📦 Data Loader Function
# --------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Load internship data from a compressed JSON (gzip) file.

    Returns:
        pd.DataFrame: DataFrame berisi data lowongan magang.
    """
    try:
        with gzip.open("data.json.gz", "rt", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame()


# Load dataset
df = load_data()

# --------------------------------------------------------------
# 📊 Data Processing & Display Logic
# --------------------------------------------------------------
if not df.empty:
    # Convert timestamp columns to datetime for consistent formatting
    for col in ["created_at", "updated_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # ----------------------------------------------------------
    # 🔍 Sidebar Filters
    # ----------------------------------------------------------
    st.sidebar.header("🔍 Filter Data")

    # Dropdown options for provinsi and kabupaten
    provinsi_list = ["Semua"] + sorted(df["provinsi"].dropna().unique())

    # Province filter
    selected_provinsi = st.sidebar.selectbox("Pilih Provinsi", provinsi_list)

    # Apply selected filters efficiently
    mask = pd.Series(True, index=df.index)
    if selected_provinsi != "Semua":
        mask &= df["provinsi"] == selected_provinsi

        # District filter (only active if a province is selected)
        kabupaten_list = ["Semua"] + sorted(df[mask]["kabupaten"].dropna().unique())
        selected_kabupaten = st.sidebar.selectbox(
            "Pilih Kabupaten",
            kabupaten_list,
            disabled=(selected_provinsi == "Semua"),
        )
        if selected_kabupaten != "Semua":
            mask &= df[mask]["kabupaten"] == selected_kabupaten

    # Keyword search
    search_query = st.sidebar.text_input("Cari Nama Posisi").strip()
    if search_query:
        mask &= df["posisi"].str.contains(search_query, case=False, na=False)

    # Apply combined mask to data
    df = df[mask]

    # ----------------------------------------------------------
    # 🔗 Add link to each job listing
    # ----------------------------------------------------------
    df["daftar"] = df["id_posisi"].apply(
        lambda x: f"https://maganghub.kemnaker.go.id/lowongan/view/{x}"
    )

    # ----------------------------------------------------------
    # 📋 Column Selection and Formatting
    # ----------------------------------------------------------
    columns_to_show = [
        "daftar",
        "posisi",
        "deskripsi_posisi",
        "diff_quota",
        "jumlah_kuota",
        "jumlah_terdaftar",
        "program_studi",
        "jenjang",
        "perusahaan",
        "government_agency",
        "sub_government_agency",
        "kabupaten",
        "provinsi",
        "created_at",
        "updated_at",
    ]
    df_display = df[columns_to_show].copy()

    # Clean column names for better presentation
    df_display.columns = df_display.columns.str.title().str.replace("_", " ")

    # ----------------------------------------------------------
    # ↕️ Sorting Controls
    # ----------------------------------------------------------
    sort_column = st.sidebar.selectbox(
        "Urutkan berdasarkan",
        options=df_display.columns[1:],  # skip 'daftar' link
        key="sort_column",
    )
    ascending = (
        st.sidebar.radio("Urutan", ["Naik (ASC)", "Turun (DESC)"]) == "Naik (ASC)"
    )
    df_display = df_display.sort_values(
        by=sort_column, ascending=ascending
    ).reset_index(drop=True)

    # ----------------------------------------------------------
    # ⚠️ Handle Empty Result
    # ----------------------------------------------------------
    if df_display.empty:
        st.warning("Tidak ada data yang sesuai dengan filter atau pencarian.")
    else:
        # ------------------------------------------------------
        # 📄 Pagination Controls
        # ------------------------------------------------------
        items_per_page = st.sidebar.slider("Jumlah baris per halaman", 10, 100, 20, 10)
        total_items = len(df_display)
        total_pages = math.ceil(total_items / items_per_page)

        # Layout columns for header and pagination
        col_header, col_pagination = st.columns([2, 1])
        with col_pagination:
            page = st.number_input(
                "Halaman",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
            )
            start, end = (page - 1) * items_per_page, page * items_per_page

        # Subset data for the selected page
        df_page = df_display.iloc[start:end].reset_index(drop=True)

        with col_header:
            st.markdown(
                f"### Menampilkan {len(df_page)} dari {total_items} data (Halaman {page}/{total_pages})"
            )

        # ------------------------------------------------------
        # 🧾 Display Interactive Table
        # ------------------------------------------------------
        st.dataframe(
            df_page,
            column_config={
                df_page.columns[0]: st.column_config.LinkColumn(
                    df_page.columns[0], help="Buka di MagangHub", display_text="Daftar"
                ),
            },
            hide_index=True,
        )

        # ------------------------------------------------------
        # 📥 CSV Download
        # ------------------------------------------------------
        csv = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Unduh CSV",
            data=csv,
            file_name="lowongan_magang.csv",
            mime="text/csv",
        )

# --------------------------------------------------------------
# 🟡 No Data Fallback
# --------------------------------------------------------------
else:
    st.warning("Tidak ada data untuk ditampilkan.")
