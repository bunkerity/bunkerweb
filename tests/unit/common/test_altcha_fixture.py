"""Exercise the fixture's actual ALTCHA v1 HTTP contract with the official SDK."""

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from threading import Barrier, Thread
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest
from altcha.v1 import Challenge, Payload, solve_challenge
from fixtures.altcha_v1 import SITES, Verifier, serve

LOCAL_HTTP = build_opener(ProxyHandler({}))


@pytest.fixture
def origins():
    with ExitStack() as stack:

        def launch(lifetime=timedelta(minutes=2)):
            urls = []
            for role in ("public", "verifier"):
                server = stack.enter_context(serve(role, "127.0.0.1", 0, Verifier(lifetime)))
                thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
                thread.start()
                stack.callback(thread.join)
                stack.callback(server.shutdown)
                urls.append(f"http://127.0.0.1:{server.server_port}")
            return tuple(urls)

        yield launch


def submit(origin, payload, secret):
    request = Request(
        f"{origin}/v1/verify/signature",
        data=json.dumps({"payload": payload, "secret": secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with LOCAL_HTTP.open(request, timeout=5) as response:
        assert response.status == 200
        return json.load(response)


def proof(origin, site="site-a"):
    with LOCAL_HTTP.open(f"{origin}/v1/challenge?apiKey={site}", timeout=5) as response:
        assert response.headers["Cache-Control"] == "no-store"
        data = json.load(response)
    challenge = Challenge(data["algorithm"], data["challenge"], data["maxNumber"], data["salt"], data["signature"])
    solved = solve_challenge(challenge)
    assert solved is not None
    return Payload(challenge.algorithm, challenge.challenge, solved.number, challenge.salt, challenge.signature).to_base64()


@pytest.mark.parametrize("site", ["site-a", "site-b"])
def test_round_trip_binds_key_and_consumes_success_only(origins, site):
    public, verifier = origins()
    solution = proof(public, site)
    other = "site-b" if site == "site-a" else "site-a"
    assert submit(verifier, solution, SITES[other].secret) == {"verified": False}
    assert submit(verifier, solution, "unknown-test-secret") == {"verified": False}
    assert submit(verifier, solution, SITES[site].secret) == {"verified": True, "apiKey": site}
    assert submit(verifier, solution, SITES[site].secret) == {"verified": False}


def test_expired_and_malformed_proofs_are_denied(origins):
    public, verifier = origins(timedelta(seconds=-2))
    assert submit(verifier, proof(public), SITES["site-a"].secret) == {"verified": False}
    assert submit(verifier, "ordinary-invalid-proof", SITES["site-a"].secret) == {"verified": False}


def test_concurrent_submissions_consume_proof_once(origins):
    public, verifier = origins()
    solution = proof(public)
    barrier = Barrier(8)

    def verify(_):
        barrier.wait(timeout=5)
        return submit(verifier, solution, SITES["site-a"].secret)["verified"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(verify, range(8))).count(True) == 1


def test_endpoints_stay_on_their_respective_origins(origins):
    public, verifier = origins()
    with pytest.raises(HTTPError, match="404"):
        submit(public, proof(public), SITES["site-a"].secret)
    with pytest.raises(HTTPError, match="404"):
        proof(verifier)
    with pytest.raises(HTTPError, match="404"):
        proof(public, "unknown-site")
