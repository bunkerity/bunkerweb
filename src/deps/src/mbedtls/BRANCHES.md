# Maintained branches

At any point in time, we have a number of maintained branches, currently consisting of:

- The [`main`](https://github.com/Mbed-TLS/mbedtls/tree/main) branch:
  this always contains the latest release, including all publicly available
  security fixes.
- The [`development`](https://github.com/Mbed-TLS/mbedtls/tree/development) branch:
  this is where the next major version of Mbed TLS (version 4.0) is being
  prepared. It has API changes that make it incompatible with Mbed TLS 3.x,
  as well as all the new features and bug fixes and security fixes.
- One or more long-time support (LTS) branches: these only get bug fixes and
  security fixes. Currently, the supported LTS branches are:
- [`mbedtls-2.28`](https://github.com/Mbed-TLS/mbedtls/tree/mbedtls-2.28).
- [`mbedtls-3.6`](https://github.com/Mbed-TLS/mbedtls/tree/mbedtls-3.6).

We retain a number of historical branches, whose names are prefixed by `archive/`,
such as [`archive/mbedtls-2.7`](https://github.com/Mbed-TLS/mbedtls/tree/archive/mbedtls-2.7).
These branches will not receive any changes or updates.

We use [Semantic Versioning](https://semver.org/). In particular, we maintain
API compatibility in the `main` branch across minor version changes (e.g.
the API of 3.(x+1) is backward compatible with 3.x). We only break API
compatibility on major version changes (e.g. from 3.x to 4.0). We also maintain
ABI compatibility within LTS branches; see the next section for details.

We will make regular LTS releases on an 18-month cycle, each of which will have
a 3 year support lifetime. On this basis, 3.6 LTS (released March 2024) will be
supported until March 2027. The next LTS release will be a 4.x release, which is
planned for September 2025.

## Backwards Compatibility for application code

We maintain API compatibility in released versions of Mbed TLS. If you have
code that's working and secure with Mbed TLS x.y.z and does not rely on
undocumented features, then you should be able to re-compile it without
modification with any later release x.y'.z' with the same major version
number, and your code will still build, be secure, and work.

Note that this guarantee only applies if you either use the default
compile-time configuration (`mbedtls/mbedtls_config.h`) or the same modified
compile-time configuration. Changing compile-time configuration options can
result in an incompatible API or ABI, although features will generally not
affect unrelated features (for example, enabling or disabling a
cryptographic algorithm does not break code that does not use that
algorithm).

Note that new releases of Mbed TLS may extend the API. Here are some
examples of changes that are common in minor releases of Mbed TLS, and are
not considered API compatibility breaks:

* Adding or reordering fields in a structure or union.
* Removing a field from a structure, unless the field is documented as public.
* Adding items to an enum.
* Returning an error code that was not previously documented for a function
  when a new error condition arises.
* Changing which error code is returned in a case where multiple error
  conditions apply.
* Changing the behavior of a function from failing to succeeding, when the
  change is a reasonable extension of the current behavior, i.e. the
  addition of a new feature.

There are rare exceptions where we break API compatibility: code that was
relying on something that became insecure in the meantime (for example,
crypto that was found to be weak) may need to be changed. In case security
comes in conflict with backwards compatibility, we will put security first,
but always attempt to provide a compatibility option.

## Backward compatibility for the key store

We maintain backward compatibility with previous versions of the
PSA Crypto persistent storage since Mbed TLS 2.25.0, provided that the
storage backend (PSA ITS implementation) is configured in a compatible way.
We intend to maintain this backward compatibility throughout a major version
of Mbed TLS (for example, all Mbed TLS 3.y versions will be able to read
keys written under any Mbed TLS 3.x with x <= y).

Mbed TLS 3.x can also read keys written by Mbed TLS 2.25.0 through 2.28.x
LTS, but future major version upgrades (for example from 2.28.x/3.x to 4.y)
may require the use of an upgrade tool.

Note that this guarantee does not currently fully extend to drivers, which
are an experimental feature. We intend to maintain compatibility with the
basic use of drivers from Mbed TLS 2.28.0 onwards, even if driver APIs
change. However, for more experimental parts of the driver interface, such
as the use of driver state, we do not yet guarantee backward compatibility.

## Long-time support branches

For the LTS branches, additionally we try very hard to also maintain ABI
compatibility (same definition as API except with re-linking instead of
re-compiling) and to avoid any increase in code size or RAM usage, or in the
minimum version of tools needed to build the code. The only exception, as
before, is in case those goals would conflict with fixing a security issue, we
will put security first but provide a compatibility option. (So far we never
had to break ABI compatibility in an LTS branch, but we occasionally had to
increase code size for a security fix.)

For contributors, see the [Backwards Compatibility section of
CONTRIBUTING](CONTRIBUTING.md#backwards-compatibility).

## Current Branches

The following branches are currently maintained:

- [main](https://github.com/Mbed-TLS/mbedtls/tree/main)
- [`development`](https://github.com/Mbed-TLS/mbedtls/)
- [`mbedtls-3.6`](https://github.com/Mbed-TLS/mbedtls/tree/mbedtls-3.6)
 maintained until March 2027, see
  <https://github.com/Mbed-TLS/mbedtls/releases/tag/v3.6.3>.

> Note: [**`mbedtls-2.28.10`**](https://github.com/Mbed-TLS/mbedtls/releases/tag/v2.28.10)
is the last release of the 2.28 LTS and won't receive bug fixes or security fixes anymore.
Users are advised to upgrade to a maintained version.

Users are urged to always use the latest version of a maintained branch.
