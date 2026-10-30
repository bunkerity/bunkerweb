## Build using Docker

Build:

```bash
docker build -t lua-resty-http-builder:test .
```

Run:

```bash
docker run --rm -it -v "$(pwd)":/src -w /src lua-resty-http-builder:test bash

# Check LUA as well as run all tests and coverage:
luacheck lib && make coverage

# Run a single test file:
luacheck lib && TEST_FILE=t/01-basic.t make coverage
```
