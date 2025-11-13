import json
import pandas as pd
from tqdm import tqdm
from requests import get
from concurrent.futures import ThreadPoolExecutor, as_completed

limit = 100
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}

url_template = (
    "https://maganghub.kemnaker.go.id/be/v1/api/list/vacancies-aktif?"
    "order_by=jumlah_terdaftar&order_direction=ASC&page={page}&limit={limit}"
)

all_data = []

def fetch_page(page):
    while True:
        try:
            res = get(
                url_template.format(page=page, limit=limit), headers=headers
            )
            if res.status_code == 200:
                data = json.loads(res.text)
                return data
        except:
            pass

def fetch_all():
    first_page_data = fetch_page(1)
    if not first_page_data or "meta" not in first_page_data:
        print("Gagal mendapatkan metadata halaman pertama.")
        return []

    meta = first_page_data["meta"]
    last_page = meta.get("pagination", {}).get("last_page", 1)

    print(f"📄 Total halaman: {last_page}")

    results = []
    results.extend(first_page_data.get("data", []))

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

all_data = fetch_all()
print(f"\n✅ Total data terkumpul: {len(all_data)}")

df = pd.DataFrame(all_data)

df.to_json(
    "raw_data.json", indent=4, orient="records", date_format="iso", date_unit="s"
)

df = df.drop_duplicates(subset=["id_posisi"]).reset_index(drop=True)

df = df.dropna(axis=1, how="all")

df[["created_at", "updated_at"]] = pd.to_datetime(
    df[["created_at", "updated_at"]].stack()
).unstack()

df["kabupaten"] = df["perusahaan"].apply(lambda x: x["nama_kabupaten"])
df["provinsi"] = df["perusahaan"].apply(lambda x: x["nama_provinsi"])

df["diff_quota"] = df["jumlah_kuota"] - df["jumlah_terdaftar"]
df = df[[df.columns[-1]] + df.columns[:-1].tolist()]

df["government_agency"] = df["government_agency"].apply(
    lambda x: x["government_agency_name"] if isinstance(x, dict) else None
)
df["sub_government_agency"] = df["sub_government_agency"].apply(
    lambda x: x["sub_government_agency_name"] if isinstance(x, dict) else None
)
df["program_studi"] = df["program_studi"].apply(
    lambda x: (
        ", ".join([i["title"] for i in json.loads(x)]) if isinstance(x, str) else None
    )
)
df["jenjang"] = df["jenjang"].apply(
    lambda x: ", ".join([i for i in eval(x)]) if isinstance(x, str) else None
)

df.to_json("data.json", indent=4, orient="records", date_format="iso", date_unit="s")

