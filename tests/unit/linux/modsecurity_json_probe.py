"""Exercise the installed ModSecurity C API; run with LIBRARY AUDIT_DIRECTORY."""

import ctypes
import json
import sys
from ctypes import POINTER as pointer_type  # codespell:ignore poin
from pathlib import Path


class Intervention(ctypes.Structure):
    _fields_ = [("status", ctypes.c_int), ("pause", ctypes.c_int), ("url", ctypes.c_void_p), ("log", ctypes.c_void_p), ("disruptive", ctypes.c_int)]


def probe(library, directory):
    lib = ctypes.CDLL(str(library))
    pointer = ctypes.c_void_p
    string = ctypes.c_char_p
    signatures = {
        "msc_init": (pointer, []),
        "msc_cleanup": (None, [pointer]),
        "msc_create_rules_set": (pointer, []),
        "msc_rules_add": (ctypes.c_int, [pointer, string, pointer_type(string)]),
        "msc_rules_cleanup": (ctypes.c_int, [pointer]),
        "msc_new_transaction": (pointer, [pointer, pointer, pointer]),
        "msc_process_connection": (ctypes.c_int, [pointer, string, ctypes.c_int, string, ctypes.c_int]),
        "msc_process_uri": (ctypes.c_int, [pointer, string, string, string]),
        "msc_add_request_header": (ctypes.c_int, [pointer, string, string]),
        "msc_process_request_headers": (ctypes.c_int, [pointer]),
        "msc_append_request_body": (ctypes.c_int, [pointer, string, ctypes.c_size_t]),
        "msc_process_request_body": (ctypes.c_int, [pointer]),
        "msc_intervention": (ctypes.c_int, [pointer, pointer_type(Intervention)]),
        "msc_intervention_cleanup": (None, [pointer_type(Intervention)]),
        "msc_process_logging": (ctypes.c_int, [pointer]),
        "msc_transaction_cleanup": (None, [pointer]),
    }
    for name, (result, args) in signatures.items():
        getattr(lib, name).restype = result
        getattr(lib, name).argtypes = args
    directory.mkdir(parents=True, exist_ok=True)
    audit = directory / "audit.log"
    assert not audit.exists(), "use a fresh audit directory"
    engine = lib.msc_init()
    rules = lib.msc_create_rules_set()
    error = string()
    config = f"""
SecRuleEngine On
SecRequestBodyAccess On
SecAuditEngine On
SecAuditLogType Serial
SecAuditLogFormat JSON
SecAuditLogParts ABCFHZ
SecAuditLog {audit}
SecRule REQUEST_HEADERS:Content-Type "@beginsWith application/json" "id:1,phase:1,pass,nolog,ctl:requestBodyProcessor=JSON"
SecRule REQBODY_ERROR "!@eq 0" "id:2,phase:2,deny,status:400,log"
SecRule ARGS:json.probe "@streq yajl-proof" "id:3,phase:2,deny,status:403,log"
"""
    statuses = []
    try:
        assert lib.msc_rules_add(rules, config.encode(), ctypes.byref(error)) >= 0, error.value
        for index, body in enumerate((b'{"probe":"yajl-proof"}', b'{"probe":"allowed"}', b'{"probe":')):
            transaction = lib.msc_new_transaction(engine, rules, None)
            try:
                lib.msc_process_connection(transaction, b"127.0.0.1", 12345, b"127.0.0.1", 80)
                lib.msc_process_uri(transaction, f"/json-proof-{index}".encode(), b"POST", b"1.1")
                lib.msc_add_request_header(transaction, b"Host", b"localhost")
                lib.msc_add_request_header(transaction, b"Content-Type", b"application/json")
                lib.msc_process_request_headers(transaction)
                lib.msc_append_request_body(transaction, body, len(body))
                lib.msc_process_request_body(transaction)
                intervention = Intervention(status=200)
                lib.msc_intervention(transaction, ctypes.byref(intervention))
                statuses.append(intervention.status)
                lib.msc_intervention_cleanup(ctypes.byref(intervention))
                lib.msc_process_logging(transaction)
            finally:
                lib.msc_transaction_cleanup(transaction)
    finally:
        lib.msc_rules_cleanup(rules)
        lib.msc_cleanup(engine)
    records = []
    remaining = audit.read_text().strip()
    while remaining:
        record, end = json.JSONDecoder().raw_decode(remaining)
        records.append(record)
        remaining = remaining[end:].lstrip()
    print(json.dumps({"statuses": statuses, "audit_records": records}, indent=2), flush=True)
    assert statuses == [403, 200, 400], f"JSON body inspection failed: {statuses}"
    assert len(records) == 3
    for index, record in enumerate(records):
        assert "error" not in record, record
        assert record["transaction"]["request"]["uri"] == f"/json-proof-{index}"


if __name__ == "__main__":
    probe(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
