
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./others/modsec_white_bg.png">
  <source media="(prefers-color-scheme: light)" srcset="./others/modsec.png">
  <img src="./others/modsec.png" width="50%">
</picture>

![Quality Assurance](https://github.com/owasp-modsecurity/ModSecurity/workflows/Quality%20Assurance/badge.svg)
[![Build Status](https://sonarcloud.io/api/project_badges/measure?project=owasp-modsecurity_ModSecurity&metric=alert_status)](https://sonarcloud.io/dashboard?id=owasp-modsecurity_ModSecurity)
[![](https://sonarcloud.io/api/project_badges/measure?project=owasp-modsecurity_ModSecurity&metric=sqale_rating
)](https://sonarcloud.io/dashboard?id=owasp-modsecurity_ModSecurity)
[![](https://sonarcloud.io/api/project_badges/measure?project=owasp-modsecurity_ModSecurity&metric=reliability_rating
)](https://sonarcloud.io/dashboard?id=owasp-modsecurity_ModSecurity)
[![](https://sonarcloud.io/api/project_badges/measure?project=owasp-modsecurity_ModSecurity&metric=security_rating
)](https://sonarcloud.io/dashboard?id=owasp-modsecurity_ModSecurity)
[![](https://sonarcloud.io/api/project_badges/measure?project=owasp-modsecurity_ModSecurity&metric=vulnerabilities
)](https://sonarcloud.io/dashboard?id=owasp-modsecurity_ModSecurity)



Libmodsecurity is one component of the ModSecurity v3 project. The library
codebase serves as an interface to ModSecurity Connectors taking in web traffic
and applying traditional ModSecurity processing. In general, it provides the
capability to load/interpret rules written in the ModSecurity SecRules format
and apply them to HTTP content provided by your application via Connectors.

If you are looking for ModSecurity for Apache (aka ModSecurity v2.x), it is still under maintenance and available:
[here](https://github.com/owasp-modsecurity/ModSecurity/tree/v2/master).

### What is the difference between this project and the old ModSecurity (v2.x.x)?

* All Apache dependencies have been removed
* Higher performance
* New features
* New architecture

Libmodsecurity is a complete rewrite of the ModSecurity platform. When it was first devised the ModSecurity project started as just an Apache module. Over time the project has been extended, due to popular demand, to support other platforms including (but not limited to) Nginx and IIS. In order to provide for the growing demand for additional platform support, it has became necessary to remove the Apache dependencies underlying this project, making it more platform independent.

As a result of this goal we have rearchitected Libmodsecurity such that it is no longer dependent on the Apache web server (both at compilation and during runtime). One side effect of this is that across all platforms users can expect increased performance. Additionally, we have taken this opportunity to lay the groundwork for some new features that users have been long seeking. For example we are looking to natively support auditlogs in the JSON format, along with a host of other functionality in future versions.


### It is no longer just a module.

The 'ModSecurity' branch no longer contains the traditional module logic (for Nginx, Apache, and IIS) that has traditionally been packaged all together. Instead, this branch only contains the library portion (libmodsecurity) for this project. This library is consumed by what we have termed 'Connectors' these connectors will interface with your webserver and provide the library with a common format that it understands. Each of these connectors is maintained as a separate GitHub project. For instance, the Nginx connector is supplied by the ModSecurity-nginx project (https://github.com/owasp-modsecurity/ModSecurity-nginx).

Keeping these connectors separated allows each project to have different release cycles, issues and development trees. Additionally, it means that when you install ModSecurity v3 you only get exactly what you need, no extras you won't be using.

# Compilation

Before starting the compilation process, make sure that all required dependencies are installed.  
See the [Dependencies](#dependencies) and [Git submodules](#Git-submodules) section for further information.

After compilation, make sure that there are no issues on your build/platform.  
We strongly recommend running the unit tests and regression tests. These test utilities are located in the [`tests/`](#testing-your-patch) subfolder.

As a dynamic library, `libmodsecurity` must be installed in a location where your operating system can find dynamic libraries.

### Unix (Linux, macOS, FreeBSD, …)

On Unix-like systems, the project uses autotools for the compilation process.

If you are working with a git checkout, make sure to clone the repository recursively or initialize all submodules before building.  
See also the [Git submodules](#git-submodules) section.

```sh
git clone https://github.com/owasp-modsecurity/ModSecurity ModSecurity
cd ModSecurity
````

This repository uses git submodules. After cloning, make sure to initialize and fetch all submodules:

```sh
git submodule update --init --recursive
```

You can verify that all submodules are properly initialized with:

```sh
git submodule status
```

Submodules that are correctly initialized show a commit hash.
A leading `-` indicates that the submodule has not been initialized.

You can then start the build process:

```sh
./build.sh
./configure
make
sudo make install
```

Details on distribution-specific builds can be found in our Wiki:
[Compilation Recipes](https://github.com/owasp-modsecurity/ModSecurity/wiki/Compilation-recipes)

### Windows

Windows build information can be found [here](build/win32/README.md).

## Dependencies

* This library is written in C++ using the C++17 standard.
* It uses Flex and Bison (Yacc) to produce the “Sec Rules Language” parser.
* Mandatory dependencies include YAJL, as ModSecurity uses JSON for logging and its testing framework.
* libXML2 (optional) is used for parsing XML requests.

### Regular expression engine (PCRE2 / PCRE)

* Regular expression processing in SecRules is implemented via the `Regex` utility (`src/utils/regex.*`).
* By default, ModSecurity uses **PCRE2** for regex handling.
* This is used by operators such as `@rx`, `@rxGlobal`, and `@verifyCC`.
* Build-time behavior:

  * **Default:** PCRE2 is detected and used.
  * **Fallback:** legacy PCRE can be used if `--with-pcre` is explicitly provided (`WITH_PCRE`).
* In other words, current builds expect PCRE2 unless explicitly configured otherwise.

All other dependencies are related to operators specified within SecRules or configuration directives and may not be required for compilation.

### Operator-related dependencies

* `libinjection` is required for the operators `@detectXSS` and `@detectSQL`.
* `curl` is required for the directive `SecRemoteRules`.

If those libraries are missing, ModSecurity will be compiled without support for the respective operators or directives.

### Git-submodules

The repository includes the following submodules:

* `others/libinjection` – used by `@detectSQLi` and `@detectXSS` operators.

* `others/mbedtls` (TF-PSA-Crypto subset) – used for cryptographic functions and helpers (e.g. hashing, base64).

  **Note:** The newer mbedTLS v4 layout is not compatible with the older v3 structure.
  The internal structure has changed significantly, and many components have been moved into submodules (e.g. TF-PSA-Crypto).

  After merging PR #3532, it is required to run:

  ```sh
  git submodule update --init --recursive
  ```

  This ensures that all required submodules are fetched. Without this step, the project will not build successfully.

  You can verify that all submodules are properly initialized with:

  ```sh
  git submodule status
  ```

  Example output:

  ```sh
  bc625d5... bindings/python
  2117822... others/libinjection (v4.0.0)
  0fe989b... others/mbedtls (v4.1.0)
  a3d4405... test/test-cases/secrules-language-tests
  ```

  If a submodule is missing, it will be shown with a leading `-`, for example:

  ```sh
  -bc625d5... bindings/python
  ```

  A leading `-` indicates that the submodule has not been initialized or fetched.

* `test/test-cases/secrules-language-tests` – shared SecRules conformance and regression test suite used by `make check`.

* `bindings/python` – Python bindings for ModSecurity (not required for core library compilation).

`others/libinjection` and `others/mbedtls` are effectively required for source builds and must be initialized before building.

### Optional external dependencies

Several external libraries are optional and enable additional features, including:

* `libcurl` – required for `SecRemoteRules`

* LMDB – persistent storage support

* Lua – scripting support

* XML libraries – extended XML processing

* **GeoIP (legacy) / MaxMind**

  The legacy **GeoIP C API** (libGeoIP) is **deprecated and no longer maintained** by MaxMind.
  The upstream repository has been archived and should not be used for new deployments.

  Instead, ModSecurity supports the modern **MaxMind DB API (libmaxminddb)**, which is actively maintained.

  During configuration you may see something like:

  ```sh
  + GeoIP/MaxMind                                 ....found
      * (MaxMind) v1.12.2
         -lmaxminddb , -I/usr/include/x86_64-linux-gnu
  ```

  This indicates that **libmaxminddb** is being used (recommended).

  It is strongly recommended to use MaxMind DB instead of the legacy GeoIP library.


# Library documentation

The library documentation is written within the code in Doxygen format. To generate this documentation, please use the doxygen utility with the provided configuration file, “doxygen.cfg”, located with the "doc/" subfolder. This will generate HTML formatted documentation including usage examples.

# Library utilization

The library provides a C++ and C interface. Some resources are currently only
available via the C++ interface, for instance, the capability to create custom logging
mechanism (see the regression test to check for how those logging mechanism works).
The objective is to have both APIs (C, C++) providing the same functionality,
if you find an aspect of the API that is missing via a particular interface, please open an issue.

Inside the subfolder examples, there are simple examples on how to use the API.
Below some are illustrated:

###  Simple example using C++

```c++
using ModSecurity::ModSecurity;
using ModSecurity::Rules;
using ModSecurity::Transaction;

ModSecurity *modsec;
ModSecurity::Rules *rules;

modsec = new ModSecurity();

rules = new Rules();

rules->loadFromUri(rules_file);

Transaction *modsecTransaction = new Transaction(modsec, rules);

modsecTransaction->processConnection("127.0.0.1");
if (modsecTransaction->intervention()) {
   std::cout << "There is an intervention" << std::endl;
}
```

### Simple example using C

```c
#include "modsecurity/modsecurity.h"
#include "modsecurity/transaction.h"


char main_rule_uri[] = "basic_rules.conf";

int main (int argc, char **argv)
{
    ModSecurity *modsec = NULL;
    Transaction *transaction = NULL;
    Rules *rules = NULL;

    modsec = msc_init();

    rules = msc_create_rules_set();
    msc_rules_add_file(rules, main_rule_uri);

    transaction = msc_new_transaction(modsec, rules);

    msc_process_connection(transaction, "127.0.0.1");
    msc_process_uri(transaction, "http://www.modsecurity.org/test?key1=value1&key2=value2&key3=value3&test=args&test=test");
    msc_process_request_headers(transaction);
    msc_process_request_body(transaction);
    msc_process_response_headers(transaction);
    msc_process_response_body(transaction);

    return 0;
}

```

# Contributing

You are more than welcome to contribute to this project and look forward to growing the community around this new version of ModSecurity. Areas of interest include: New
functionalities, fixes, bug report, support for beginning users, or anything that you
are willing to help with.

## Providing patches

We prefer to have your patch within the GitHub infrastructure to facilitate our
review work, and our Q.A. integration. GitHub provides excellent
documentation on how to perform “Pull Requests”, more information available
here: https://help.github.com/articles/using-pull-requests/

Please respect the coding style. Pull requests can include various commits, so
provide one fix or one piece of functionality per commit. Please do not change anything outside
the scope of your target work (e.g. coding style in a function that you have
passed by). For further information about the coding style used in this
project, please check: https://www.chromium.org/blink/coding-style

Provides explanative commit messages. Your first line should  give the highlights of your
patch, 3rd and on give a more detailed explanation/technical details about your
patch. Patch explanation is valuable during the review process.

### Don’t know where to start?

Within our code there are various items marked as TODO or FIXME that may need
your attention. Check the list of items by performing a grep:

```
$ cd /path/to/modsecurity-nginx
$ egrep -Rin "TODO|FIXME" -R *
```

A TODO list is also available as part of the Doxygen documentation.

### Testing your patch

Along with the manual testing, we strongly recommend you to use the our
regression tests and unit tests. If you have implemented an operator, don’t
forget to create unit tests for it. If you implement anything else, it is encouraged that you develop complimentary regression tests for it.

The regression test and unit test utilities are native and do not demand any
external tool or script, although you need to fetch the test cases from other
repositories, as they are shared with other versions of ModSecurity, those
others repositories git submodules. To fetch the submodules repository and run
the utilities, follow the commands listed below:

```shell
$ cd /path/to/your/ModSecurity
$ git submodule update --init --recursive
$ make check
 ```

### Debugging


Before start the debugging process, make sure of where your bug is. The problem
could be on your connector or in libmodsecurity. In order to identify where the
bug is, it is recommended that you develop a regression test that mimics the
scenario where the bug is happening. If the bug is reproducible with the
regression-test utility, then it will be far simpler to debug and ensure that it never occurs again. On Linux it is
recommended that anyone undertaking debugging utilize gdb and/or valgrind as needed.

During the configuration/compilation time, you may want to disable the compiler
optimization making your “back traces” populated with readable data. Use the
CFLAGS to disable the compilation optimization parameters:

```shell
$ export CFLAGS="-g -O0"
$ ./build.sh
$ ./configure --enable-assertions=yes
$ make
$ sudo make install
```
"Assertions allow us to document assumptions and to spot violations early in the
development process. What is more, assertions allow us to spot violations with a
minimum of effort." https://dl.acm.org/doi/pdf/10.1145/240964.240969

It is recommended to use assertions where applicable, and to enable them with
'--enable-assertions=yes' during the testing and debugging workflow.

### Benchmarking

The source tree includes a Benchmark tool that can help measure library performance. The tool is located in the `test/benchmark/` directory. The build process also creates the binary here, so you will have the tool after the compilation is finished.

To run, just type:

```shell
cd test/benchmark
$ ./benchmark
Doing 1000000 transactions...

```

You can also pass a lower value:

```shell
$ ./benchmark 1000
Doing 1000 transactions...
```

To measure the time:
```shell
$ time ./benchmark 1000
Doing 1000 transactions...

real	0m0.351s
user	0m0.337s
sys	0m0.022s
```

This is very fast because the benchmark uses the minimal `modsecurity.conf.default` configuration, which doesn't include too many rules:

```shell
$ cat basic_rules.conf

Include "../../modsecurity.conf-recommended"

```

To measure with real rules, run one of the download scripts in the same directory:

```shell
$ ./download-owasp-v3-rules.sh
Cloning into 'owasp-v3'...
remote: Enumerating objects: 33007, done.
remote: Counting objects: 100% (2581/2581), done.
remote: Compressing objects: 100% (907/907), done.
remote: Total 33007 (delta 2151), reused 2004 (delta 1638), pack-reused 30426
Receiving objects: 100% (33007/33007), 9.02 MiB | 16.21 MiB/s, done.
Resolving deltas: 100% (25927/25927), done.
Switched to a new branch 'tag3.0.2'
/path/to/ModSecurity/test/benchmark
Done.

$ cat basic_rules.conf

Include "../../modsecurity.conf-recommended"

Include "owasp-v3/crs-setup.conf.example"
Include "owasp-v3/rules/*.conf"
```

Now the command will give much higher value.

#### How the benchmark works

The tool is a straightforward wrapper application that utilizes the library. It creates a ModSecurity instance and a RuleSet instance, then runs a loop based on the specified number. Within this loop, it creates a Transaction object to emulate real HTTP transactions.

Each transaction is an HTTP/1.1 GET request with some GET parameters. Common headers are added, followed by the response headers and an XML body. Between phases, the tool checks whether an intervention has occurred. All transactions are created with the same data.

Note that the tool does not call the last phase (logging).

Please remember to reset `basic_rules.conf` if you want to try with a different ruleset.

## Reporting Issues

If you are facing a configuration issue or something is not working as you
expected to be, please use the ModSecurity user’s mailing list. Issues on GitHub
are also welcomed, but we prefer to have user ask questions on the mailing list first so that you can reach an entire community. Also don’t forget to look for existing issues before open a new one.

If you are going to open a new issue on GitHub, don’t forget to tell us the
version of your libmodsecurity and the version of a specific connector if there
is one.


### Security issue

Please do not make public any security issue. Contact us at:
modsecurity@owasp.org reporting the issue. Once the problem is fixed your
credit will be given.

## Feature request

We are open to discussing any new feature request with the community via the mailing lists. You can alternativly,
feel free to open GitHub issues requesting new features. Before opening a
new issue, please check if there is one already opened on the same topic.

## Bindings

The libModSecurity design allows the integration with bindings. There is an effort to avoid breaking API [binary] compatibility to make an easy integration with possible bindings. Currently, there are a few notable projects maintained by the community:
   * Python - https://github.com/actions-security/pymodsecurity
   * Rust - https://github.com/rkrishn7/rust-modsecurity
   * Varnish - https://github.com/xdecock/vmod-modsecurity

## Packaging

Having our packages in distros on time is a desire that we have, so let us know
if there is anything we can do to facilitate your work as a packager.

## Sponsor Note

Development of ModSecurity is sponsored by Trustwave. Sponsorship will end July 1, 2024. Additional information can be found here https://www.trustwave.com/en-us/resources/security-resources/software-updates/end-of-sale-and-trustwave-support-for-modsecurity-web-application-firewall/
