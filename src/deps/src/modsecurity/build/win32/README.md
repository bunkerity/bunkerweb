# libModSecurity Windows build information <!-- omit from toc -->

The Windows build of libModSecurity uses Build Tools for Visual Studio 2022 (for Visual C++ & CMake) and Conan package manager.

## Contents <!-- omit from toc -->

- [Prerequisites](#prerequisites)
- [Build](#build)
  - [Optional features](#optional-features)
  - [Address Sanitizer](#address-sanitizer)
  - [Docker container](#docker-container)

## Prerequisites

 * [Build Tools for Visual Studio 2022](https://aka.ms/vs/17/release/vs_buildtools.exe)
    * Install *Desktop development with C++* workload, which includes:
        * MSVC C++ compiler
        * Windows SDK
        * CMake
        * Address Sanitizer
 * [Conan package manager 2.10.2](https://github.com/conan-io/conan/releases/download/2.10.2/conan-2.10.2-windows-x86_64-installer.exe)
    * Install and then setup the default Conan profile to use the MSVC C++ compiler:
      1. Open a command-prompt and set the MSVC C++ compiler environment by executing: `C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat`
      2. Execute: `conan profile detect --force`
 * [Git for Windows 2.44.0](https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe)
    * To clone the libModSecurity repository.
    * NOTE: Make sure to initialize and update submodules (to get `libinjection` and regression tests)
      * `git submodule init`
      * `git submodule update`

## Build

Install the prerequisites listed in the previous section, checkout libModSecurity and from the directory where it's located execute:

```
vcbuild.bat [build_configuration] [arch] [USE_ASAN]
```

where `[build_configuration]` can be: `Release` (default), `RelWithDebInfo`, `MinSizeRel` or `Debug`, and `[arch]` can be: `x86_64` (default) or `x86`.

Built files will be located in the directory: `build\win32\build\[build_configuration]` and include:

 * `libModSecurity.dll`
 * Executable files for test projects
    * `unit_tests.exe`
    * `regression_tests.exe`
    * `benchmark.exe` 
    * `rules_optimization.exe`
 * Executable files for examples
    * `simple_example_using_c.exe`
    * `using_bodies_in_chunks.exe`
    * `reading_logs_via_rule_message.exe`
    * `reading_logs_with_offset.exe`
    * `multithread.exe`
 * Executable files for tools
    * `rules_check.exe`

NOTE: When building a different configuration, it's recommended to reset:

 * the build directory: `build\win32\build`
 * previously built conan packages executing the command:
    * `conan remove * -c`

### Optional features

By default the following all the following features are enabled by including the associated third-party library through a Conan package:

 * libxml2 2.12.6 for XML processing support
 * libcurl 8.6.0 to support http requests from rules
 * libmaxminddb 1.9.1 to support reading MaxMind DB files.
 * LUA 5.4.6 to enable rules to run scripts in this language for extensibility
 * lmdb 0.9.31 in-memory database

Each of these can be turned off by updating the associated `HAVE_xxx` variable (setting it to zero) in the beginning of the libModSecurity section of `CMakeLists.txt`.

### Address Sanitizer

[AddressSanitizer](https://github.com/google/sanitizers/wiki/AddressSanitizer) (aka ASan) is a memory error detector for C/C++.

To generate a build with *Address Sanitizer*, add the `USE_ASAN` optional third argument to `vcbuild.bat`. For example:
   * `vcbuild.bat Debug x86_64 USE_ASAN`

NOTE: `USE_ASAN` does not work with `Release` & `MinSizeRel` configurations because they do not include debug info (it is only compatible with `Debug` & `RelWithDebInfo` builds).

 * References
   * [AddressSanitizer | Microsoft Learn](https://learn.microsoft.com/en-us/cpp/sanitizers/asan?view=msvc-170)
   * [AddressSanitizer for Windows: x64 and Debug Build Support - C++ Team Blog (microsoft.com)](https://devblogs.microsoft.com/cppblog/asan-for-windows-x64-and-debug-build-support/)
   * [AddressSanitizer language, build, and debugging reference | Microsoft Learn](https://learn.microsoft.com/en-us/cpp/sanitizers/asan-building?view=msvc-170)

### Docker container

A `Dockerfile` configuration file is provided in the `docker` subdir that creates a Windows container image which installs the [prerequisites](#prerequisites) and builds libModSecurity and other binaries.

NOTE: Windows containers are supported in Docker Desktop for Windows, using the *Switch to Windows containers...* option on the context menu of the system tray icon.

To build the docker image, execute the following command (from the `build\win32\docker` directory):

 * `docker build -t libmodsecurity:latest -m 4GB .`
   * Build type, architecture and build with Address Sanitizer can be configured through build arguments (`BUILD_TYPE`, `ARCH` & `USE_ASAN` respectively). For example, to generate a debug build, add the following argument:
     * `--build-arg BUILD_TYPE=Debug`

Once the image is generated, the library and associated binaries (tests & examples) are located in the `C:\src\ModSecurity\build\win32\build\[build_type]` directory.

To extract the library (`libModSecurity.dll`) from the image, you can execute the following commands:

 * `docker container create --name [container_name] libmodsecurity`
 * `docker cp [container_name]:C:\src\ModSecurity\build\win32\build\[build_type]\libModSecurity.dll .`
   * NOTE: If you leave out the `libModSecurity.dll` filename out, you can copy all the built binaries (including examples & tests).

Additionally, the image can be used interactively for additional development work by executing:

 * `docker run -it libmodsecurity`
