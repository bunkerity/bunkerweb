from datetime import date
from gzip import GzipFile
from io import BytesIO
from pathlib import Path
from maxminddb import MODE_FD, open_database
from requests import get

# Compute the mmdb URL
mmdb_url = f"https://download.db-ip.com/free/dbip-asn-lite-{date.today().strftime('%Y-%m')}.mmdb.gz"

# Download the mmdb file in memory
print(f"Downloading mmdb file from url {mmdb_url} ...", flush=True)
file_content = BytesIO()
with get(mmdb_url, stream=True) as resp:
    resp.raise_for_status()
    for chunk in resp.iter_content(chunk_size=4 * 1024):
        if chunk:
            file_content.write(chunk)
file_content.seek(0)

with open_database(GzipFile(fileobj=file_content, mode="rb"), mode=MODE_FD) as reader:
    dbip_asn = reader.get("1.0.0.3")

    if not dbip_asn:
        print(f"❌ Error while reading mmdb file from {mmdb_url}", flush=True)
        exit(1)

    print(
        f"✅ ASN for IP 1.0.0.3 is {dbip_asn['autonomous_system_number']}, saving it to /output/ip_asn.txt",
        flush=True,
    )

    Path("/output/ip_asn.txt").write_text(str(dbip_asn["autonomous_system_number"]))
