import re
from pathlib import Path


def test_response_compression_runs_after_modsecurity():
    config = Path(__file__).resolve().parents[3] / "src/common/confs/nginx.conf"
    modules = re.findall(r"^load_module\s+\S*/(\w+\.so);", config.read_text(), re.MULTILINE)
    compressors = [name for name in modules if re.fullmatch(r"ngx_http_(brotli|zstd)_filter_module\.so", name)]
    assert "ngx_http_brotli_filter_module.so" in compressors
    assert all(modules.index(name) < modules.index("ngx_http_modsecurity_module.so") for name in compressors)
