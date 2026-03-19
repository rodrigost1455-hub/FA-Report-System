"""
upload_template.py — version simple, solo usa 'requests'
Compatible con Python 3.14+
"""
import argparse
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


def upload(pdf_path, supabase_url, supabase_key, bucket):
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        print(f"✗ No se encontro el archivo: {pdf_path}")
        sys.exit(1)

    print(f"→ Subiendo {pdf_file.name} ({pdf_file.stat().st_size // 1024} KB)...")

    storage_path = "templates/FA_BEC_2.pdf"
    url = f"{supabase_url}/storage/v1/object/{bucket}/{storage_path}"

    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type":  "application/pdf",
        "x-upsert":      "true",
    }

    with open(pdf_path, "rb") as f:
        response = requests.post(url, headers=headers, data=f)

    if response.status_code in (200, 201):
        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{storage_path}"
        print(f"\n✓ Template subido exitosamente")
        print(f"\n  Pega esto en Railway como variable de entorno:")
        print(f"\n  TEMPLATE_PDF_URL={public_url}\n")
    else:
        print(f"✗ Error {response.status_code}: {response.text}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf",          required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--supabase-key", required=True)
    parser.add_argument("--bucket",       default="fa-reports")
    args = parser.parse_args()
    upload(args.pdf, args.supabase_url, args.supabase_key, args.bucket)