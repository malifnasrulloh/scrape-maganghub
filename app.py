import json
import math
import gzip
import shutil
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Data Lowongan Magang", layout="wide")

st.title("📊 Data Lowongan Magang - KEMNAKER")
st.markdown(
    "Menampilkan data hasil scraping lowongan magang aktif dari "
    "[maganghub.kemnaker.go.id](https://maganghub.kemnaker.go.id)"
)


@st.cache_data
def load_data():
    try:
        with gzip.open("data.json.gz", "rt", encoding="utf-8") as f:
            data = json.load(f)
            df = pd.DataFrame(data)
            return df
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame()


df = load_data()

if not df.empty:
    df[["created_at", "updated_at"]] = pd.to_datetime(
        df[["created_at", "updated_at"]].stack()
    ).unstack()

    st.sidebar.header("🔍 Filter Data")

    provinsi_list = df["provinsi"].dropna().sort_values().unique().tolist()
    selected_provinsi = st.sidebar.multiselect("Pilih Provinsi", provinsi_list)
    if selected_provinsi:
        df = df[df["provinsi"].isin(selected_provinsi)]

    kabupaten_list = df["kabupaten"].dropna().sort_values().unique().tolist()
    selected_kabupaten = st.sidebar.multiselect("Pilih Kabupaten", kabupaten_list)
    if selected_kabupaten:
        df = df[df["kabupaten"].isin(selected_kabupaten)]

    search_posisi = st.sidebar.text_input("Cari Nama Posisi")
    if search_posisi:
        df = df[df["posisi"].str.contains(search_posisi, case=False, na=False)]

    df["daftar"] = df["id_posisi"].apply(
        lambda x: f"https://maganghub.kemnaker.go.id/lowongan/view/{x}"
    )

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
    df_display = df[columns_to_show]

    sort_column = st.sidebar.selectbox(
        "Sort Data by",
        options=columns_to_show[1:],  # exclude "daftar"
        key="sort_column",
    )
    sort_order = st.sidebar.selectbox(
        "Sort Order",
        options=["ASC", "DSC"],
        key="sort_order",
    )
    df_display = df_display.sort_values(
        by=sort_column, ascending=True if sort_order == "ASC" else False
    ).reset_index(drop=True)

    items_per_page = st.sidebar.slider("Jumlah baris per halaman", 10, 100, 20, 10)
    total_items = len(df_display)
    total_pages = math.ceil(total_items / items_per_page)

    cols = st.columns([2, 1])
    with cols[1]:
        page = st.number_input(
            "Halaman",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
        )
        start = (page - 1) * items_per_page
        end = start + items_per_page
    df_page = df_display.iloc[start:end].reset_index(drop=True)
    with cols[0]:
        st.markdown(
            f"### Menampilkan {len(df_page)} dari {total_items} data (Halaman {page}/{total_pages})"
        )

    df_page.columns = (
        df_page.columns.str.title().str.replace("_", " ").str.replace("Id", "ID")
    )
    st.dataframe(
        df_page,
        column_config={
            df_page.columns[0]: st.column_config.LinkColumn(
                df_page.columns[0], help="Forward to MagangHub", display_text=r"Daftar"
            ),
        },
        hide_index=True,
    )

    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Unduh CSV",
        data=csv,
        file_name="lowongan_magang.csv",
        mime="text/csv",
    )

else:
    st.warning("Tidak ada data untuk ditampilkan.")
