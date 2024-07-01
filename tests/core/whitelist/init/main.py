from datetime import date, timedelta
from gzip import GzipFile
from io import BytesIO
from os import getenv, sep
from maxminddb import MODE_FD, open_database
from pathlib import Path
from requests import get

current_date = date.today()

# Compute the mmdb URL
mmdb_url = f"https://download.db-ip.com/free/dbip-asn-lite-{current_date.strftime('%Y-%m')}.mmdb.gz"

# Download the mmdb file in memory
print(f"Downloading mmdb file from url {mmdb_url} ...", flush=True)

resp = get(mmdb_url, stream=True)

if resp.status_code == 404:
    print(f"⚠ No mmdb file found for {current_date.strftime('%Y-%m')}, trying with previous month ...", flush=True)
    current_date = current_date - timedelta(days=current_date.day)
    resp = get(f"https://download.db-ip.com/free/dbip-asn-lite-{current_date.strftime('%Y-%m')}.mmdb.gz", stream=True)

resp.raise_for_status()

file_content = BytesIO()
for chunk in resp.iter_content(chunk_size=4 * 1024):
    if chunk:
        file_content.write(chunk)
file_content.seek(0)

output_path = Path(sep, "output", "ip_asn.txt") if getenv("TEST_TYPE", "docker") == "docker" else Path(".", "ip_asn.txt")

with open_database(GzipFile(fileobj=file_content, mode="rb"), mode=MODE_FD) as reader:  # type: ignore
    dbip_asn = reader.get("1.0.0.3")

    if not dbip_asn:
        print(f"❌ Error while reading mmdb file from {mmdb_url}", flush=True)
        exit(1)

    print(
        f"✅ ASN for IP 1.0.0.3 is {dbip_asn['autonomous_system_number']}, saving it to {output_path}",  # type: ignore
        flush=True,
    )

    output_path.write_text(str(dbip_asn["autonomous_system_number"]))  # type: ignore
