"""
MagangHub Scraper
=================
This script scrapes active internship listings from maganghub.kemnaker.go.id's public API.

Features:
- Fetches all available pages concurrently using ThreadPoolExecutor.
- Cleans, normalizes, and transforms the dataset.
- Exports the raw and processed data into JSON and compressed GZIP JSON files.

Requirements:
- requests
- pandas
- tqdm

Author: Muhammad Alif Nasrulloh
"""

import json
import gzip
import time
import shutil
import pandas as pd
from tqdm import tqdm
from requests import get
from concurrent.futures import ThreadPoolExecutor, as_completed

# --------------------------------------------------------------
# ⚙️ Configuration
# --------------------------------------------------------------
limit = 100  # number of results per page
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
}
url_template = (
    "https://maganghub.kemnaker.go.id/be/v1/api/list/vacancies-aktif?"
    "order_by=jumlah_terdaftar&order_direction=ASC&page={page}&limit={limit}"
)

# Global data container
all_data = []


# --------------------------------------------------------------
# 🌐 Function: fetch_page()
# --------------------------------------------------------------
def fetch_page(page: int) -> dict | None:
    """
    Fetch a single page from the MagangHub API with retry logic.

    Args:
        page (int): Page number to fetch.

    Returns:
        dict | None: Parsed JSON data if successful, else None.
    """
    retries = 3
    for _ in range(retries):
        try:
            res = get(
                url_template.format(page=page, limit=limit),
                headers=headers,
                timeout=10,
            )
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        time.sleep(2)
    return None


# --------------------------------------------------------------
# 🚀 Function: fetch_all()
# --------------------------------------------------------------
def fetch_all() -> list:
    """
    Fetch all internship pages concurrently.

    Returns:
        list: A list of all internship data across all pages.
    """
    first_page_data = fetch_page(1)
    if not first_page_data or "meta" not in first_page_data:
        print("❌ Gagal mendapatkan metadata halaman pertama.")
        return []

    # Determine total page count
    meta = first_page_data["meta"]
    last_page = meta.get("pagination", {}).get("last_page", 1)
    print(f"📄 Total halaman: {last_page}")

    # Initialize results with first page
    results = list(first_page_data.get("data", []))

    # Fetch remaining pages concurrently
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_page, page): page for page in range(2, last_page + 1)
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Mengunduh data"
        ):
            page = futures[future]
            try:
                page_data = future.result()
                if page_data and "data" in page_data:
                    results.extend(page_data["data"])
            except Exception as e:
                print(f"❌ Gagal ambil halaman {page}: {e}")

    return results


# --------------------------------------------------------------
# 🧩 Main Execution
# --------------------------------------------------------------
if __name__ == "__main__":
    all_data = fetch_all()
    print(f"\n✅ Total data terkumpul: {len(all_data)}")

    # Convert to DataFrame
    df = pd.DataFrame(all_data)

    if df.empty:
        print("❌ Tidak ada data untuk diproses.")
    else:
        # ----------------------------------------------------------
        # 💾 Save Raw Data
        # ----------------------------------------------------------
        df.to_json(
            "raw_data.json",
            indent=4,
            orient="records",
            date_format="iso",
            date_unit="s",
        )
        with open("raw_data.json", "rb") as f_in, gzip.open(
            "raw_data.json.gz", "wb"
        ) as f_out:
            shutil.copyfileobj(f_in, f_out)

        # ----------------------------------------------------------
        # 🧹 Data Cleaning & Transformation
        # ----------------------------------------------------------

        # Remove duplicates by job ID
        df = df.drop_duplicates(subset=["id_posisi"]).reset_index(drop=True)

        # Drop columns that contain only NaN
        df = df.dropna(axis=1, how="all")

        # Convert timestamp columns to datetime
        for col in ["created_at", "updated_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Extract kabupaten and provinsi from nested perusahaan dict
        df["kabupaten"] = df["perusahaan"].apply(
            lambda x: x.get("nama_kabupaten") if isinstance(x, dict) else None
        )
        df["kabupaten"] = df["kabupaten"].str.strip()
        df["provinsi"] = df["perusahaan"].apply(
            lambda x: x.get("nama_provinsi") if isinstance(x, dict) else None
        )
        df["provinsi"] = df["provinsi"].str.strip()

        # Calculate remaining quota
        df["diff_quota"] = df["jumlah_kuota"] - df["jumlah_terdaftar"]

        # Reorder columns: put diff_quota at the start
        cols = ["diff_quota"] + [c for c in df.columns if c != "diff_quota"]
        df = df[cols]

        # Normalize government agency columns
        df["government_agency"] = df["government_agency"].apply(
            lambda x: x.get("government_agency_name") if isinstance(x, dict) else None
        )
        df["sub_government_agency"] = df["sub_government_agency"].apply(
            lambda x: (
                x.get("sub_government_agency_name") if isinstance(x, dict) else None
            )
        )

        # Parse program_studi JSON string safely
        def parse_program_studi(x):
            """Safely parse program_studi JSON field."""
            if isinstance(x, str):
                try:
                    return ", ".join([i["title"] for i in json.loads(x)])
                except Exception:
                    return None
            return None

        df["program_studi"] = df["program_studi"].apply(parse_program_studi)

        # Parse jenjang field (list or string)
        def parse_jenjang(x):
            """Convert jenjang list string into comma-separated values."""
            if isinstance(x, str):
                try:
                    parsed = eval(x)
                    if isinstance(parsed, list):
                        return ", ".join(parsed)
                except Exception:
                    return None
            return None

        df["jenjang"] = df["jenjang"].apply(parse_jenjang)

        # ----------------------------------------------------------
        # 💾 Save Cleaned Data
        # ----------------------------------------------------------
        df.to_json(
            "data.json", indent=4, orient="records", date_format="iso", date_unit="s"
        )
        with open("data.json", "rb") as f_in, gzip.open("data.json.gz", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        print("✅ Data berhasil disimpan sebagai 'data.json' dan 'data.json.gz'.")
