## Reporting Vulnerabilities

If you think you have found an Mbed TLS security vulnerability, then please
send an email to the security team at
<mbed-tls-security@lists.trustedfirmware.org>.

## Security Incident Handling Process

Our security process is detailed in our
[security
center](https://developer.trustedfirmware.org/w/mbed-tls/security-center/).

Its primary goal is to ensure fixes are ready to be deployed when the issue
goes public.

## Maintained branches

Only the maintained branches, as listed in [`BRANCHES.md`](BRANCHES.md),
get security fixes.
Users are urged to always use the latest version of a maintained branch.

## Threat model

We classify attacks based on the capabilities of the attacker.

### Remote attacks

In this section, we consider an attacker who can observe and modify data sent
over the network. This includes observing the content and timing of individual
packets, as well as suppressing or delaying legitimate messages, and injecting
messages.

Mbed TLS aims to fully protect against remote attacks and to enable the user
application in providing full protection against remote attacks. Said
protection is limited to providing security guarantees offered by the protocol
being implemented. (For example Mbed TLS alone won't guarantee that the
messages will arrive without delay, as the TLS protocol doesn't guarantee that
either.)

**Warning!** Block ciphers do not yet achieve full protection against attackers
who can measure the timing of packets with sufficient precision. For details
and workarounds see the [Block Ciphers](#block-ciphers) section.

### Local attacks

In this section, we consider an attacker who can run software on the same
machine. The attacker has insufficient privileges to directly access Mbed TLS
assets such as memory and files.

#### Timing attacks

The attacker is able to observe the timing of instructions executed by Mbed TLS
by leveraging shared hardware that both Mbed TLS and the attacker have access
to. Typical attack vectors include cache timings, memory bus contention and
branch prediction.

Mbed TLS provides limited protection against timing attacks. The cost of
protecting against timing attacks widely varies depending on the granularity of
the measurements and the noise present. Therefore the protection in Mbed TLS is
limited. We are only aiming to provide protection against **publicly
documented attack techniques**.

As attacks keep improving, so does Mbed TLS's protection. Mbed TLS is moving
towards a model of fully timing-invariant code, but has not reached this point
yet.

**Remark:** Timing information can be observed over the network or through
physical side channels as well. Remote and physical timing attacks are covered
in the [Remote attacks](remote-attacks) and [Physical
attacks](physical-attacks) sections respectively.

**Warning!** Block ciphers do not yet achieve full protection. For
details and workarounds see the [Block Ciphers](#block-ciphers) section.

#### Local non-timing side channels

The attacker code running on the platform has access to some sensor capable of
picking up information on the physical state of the hardware while Mbed TLS is
running. This could for example be an analogue-to-digital converter on the
platform that is located unfortunately enough to pick up the CPU noise.

Mbed TLS doesn't make any security guarantees against local non-timing-based
side channel attacks. If local non-timing attacks are present in a use case or
a user application's threat model, they need to be mitigated by the platform.

#### Local fault injection attacks

Software running on the same hardware can affect the physical state of the
device and introduce faults.

Mbed TLS doesn't make any security guarantees against local fault injection
attacks. If local fault injection attacks are present in a use case or a user
application's threat model, they need to be mitigated by the platform.

### Physical attacks

In this section, we consider an attacker who has access to physical information
about the hardware Mbed TLS is running on and/or can alter the physical state
of the hardware (e.g. power analysis, radio emissions or fault injection).

Mbed TLS doesn't make any security guarantees against physical attacks. If
physical attacks are present in a use case or a user application's threat
model, they need to be mitigated by physical countermeasures.

### Caveats

#### Out-of-scope countermeasures

Mbed TLS has evolved organically and a well defined threat model hasn't always
been present. Therefore, Mbed TLS might have countermeasures against attacks
outside the above defined threat model.

The presence of such countermeasures don't mean that Mbed TLS provides
protection against a class of attacks outside of the above described threat
model. Neither does it mean that the failure of such a countermeasure is
considered a vulnerability.

#### Block ciphers

Currently there are four block ciphers in Mbed TLS: AES, CAMELLIA, ARIA and
DES. The pure software implementation in Mbed TLS implementation uses lookup
tables, which are vulnerable to timing attacks.

These timing attacks can be physical, local or depending on network latency
even a remote. The attacks can result in key recovery.

**Workarounds:**

- Turn on hardware acceleration for AES. This is supported only on selected
  architectures and currently only available for AES. See configuration options
  `MBEDTLS_AESCE_C`, `MBEDTLS_AESNI_C` and `MBEDTLS_PADLOCK_C` for details.
- Add a secure alternative implementation (typically hardware acceleration) for
  the vulnerable cipher. See the [Alternative Implementations
Guide](docs/architecture/alternative-implementations.md) for more information.
- Use cryptographic mechanisms that are not based on block ciphers. In
  particular, for authenticated encryption, use ChaCha20/Poly1305 instead of
  block cipher modes. For random generation, use HMAC\_DRBG instead of CTR\_DRBG.

#### Everest

The HACL* implementation of X25519 taken from the Everest project only protects
against remote timing attacks. (See their [Security
Policy](https://github.com/hacl-star/hacl-star/blob/main/SECURITY.md).)

The Everest variant is only used when `MBEDTLS_ECDH_VARIANT_EVEREST_ENABLED`
configuration option is defined. This option is off by default.

#### Formatting of X.509 certificates and certificate signing requests

When parsing X.509 certificates and certificate signing requests (CSRs),
Mbed TLS does not check that they are strictly compliant with X.509 and other
relevant standards. In the case of signed certificates, the signing party is
assumed to have performed this validation (and the certificate is trusted to
be correctly formatted as long as the signature is correct).
Similarly, CSRs are implicitly trusted by Mbed TLS to be standards-compliant.

**Warning!** Mbed TLS must not be used to sign untrusted CSRs unless extra
validation is performed separately to ensure that they are compliant to the
relevant specifications. This makes Mbed TLS on its own unsuitable for use in
a Certificate Authority (CA).

However, Mbed TLS aims to protect against memory corruption and other
undefined behavior when parsing certificates and CSRs. If a CSR or signed
certificate causes undefined behavior when it is parsed by Mbed TLS, that
is considered a security vulnerability.
