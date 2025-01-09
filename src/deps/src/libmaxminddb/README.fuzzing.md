# Fuzzing libmaxminddb

These tests are only meant to be run on GNU/Linux.

## Build maxminddb fuzzer using libFuzzer.

### Export flags for fuzzing.

Note that in `CFLAGS` and `CXXFLAGS`, any type of sanitizers can be added.

- [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html),
    [ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html),
    [MemorySanitizer](https://clang.llvm.org/docs/MemorySanitizer.html),
    [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html),
    [LeakSanitizer](https://clang.llvm.org/docs/LeakSanitizer.html).

```shell
$ export CC=clang
$ export CXX=clang++
$ export CFLAGS="-g -DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION -fsanitize=address,undefined -fsanitize=fuzzer-no-link"
$ export CXXFLAGS="-g -DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION -fsanitize=address,undefined -fsanitize=fuzzer-no-link"
$ export LIB_FUZZING_ENGINE="-fsanitize=fuzzer"
```

### Build maxminddb for fuzzing.

```shell
$ mkdir -p build && cd build
$ cmake -DBUILD_FUZZING=ON ../.
$ cmake --build . -j$(nproc)
```

### Running fuzzer.

```shell
$ mkdir -p fuzz_mmdb_seed fuzz_mmdb_seed_corpus
$ find ../t/maxmind-db/test-data/ -type f -size -4k -exec cp {} ./fuzz_mmdb_seed_corpus/ \;
$ ./t/fuzz_mmdb fuzz_mmdb_seed/ fuzz_mmdb_seed_corpus/
```

Here is more information about [LibFuzzer](https://llvm.org/docs/LibFuzzer.html).
