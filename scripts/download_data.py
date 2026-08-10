"""Download and extract the IMDb datasets required by this project into data/.

Usage:
    uv run scripts/download_data.py
"""

import gzip
import shutil
import urllib.request
from pathlib import Path

BASE_URL = "https://datasets.imdbws.com"
FILES = [
    "title.basics.tsv.gz",
    "title.principals.tsv.gz",
    "name.basics.tsv.gz",
    "title.ratings.tsv.gz",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download_and_extract(filename: str) -> None:
    gz_path = DATA_DIR / filename
    tsv_path = gz_path.with_suffix("")

    print(f"Downloading {filename}...")
    urllib.request.urlretrieve(f"{BASE_URL}/{filename}", gz_path)

    print(f"Extracting {filename}...")
    with gzip.open(gz_path, "rb") as f_in, open(tsv_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    gz_path.unlink()
    print(f"Saved data/{tsv_path.name}")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for filename in FILES:
        download_and_extract(filename)
    print("\nAll datasets downloaded to data/")


if __name__ == "__main__":
    main()
