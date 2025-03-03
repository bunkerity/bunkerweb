# Security Policy

## Supported Versions

OWASP CRS has two types of releases, Major releases (3.0.0, 3.1.0, 3.2.0 etc.) and point releases (3.0.1, 3.0.2 etc.).
For more information see our [wiki](https://github.com/coreruleset/coreruleset/wiki/Release-Policy).

The OWASP CRS officially supports the two latest point releases with severe security patches.
We are happy to receive and merge PR's that address security issues in older versions of the project, but the team itself may choose not to fix these.
Along those lines, OWASP CRS team may not issue security notifications for unsupported software.

| Version   | Supported          |
| --------- | ------------------ |
| 4.12.z    | :white_check_mark: |
| 4.11.z    | :white_check_mark: |
| 4.y.z     | :x: |
| 3.3.x     | :white_check_mark: |
| 3.2.x     | :x:                |
| 3.1.x     | :x:                |
| 3.0.x     | :x:                |
| 2.x       | :x:                |

## GPG Signed Releases

Releases are signed using [our GPG key](https://coreruleset.org/security.asc), (fingerprint: 3600 6F0E 0BA1 6783 2158 8211 38EE ACA1 AB8A 6E72). You can verify the release using GPG/PGP compatible tooling.

### Importing the GPG Key

To get our key using gpg: `gpg --keyserver pgp.mit.edu --recv 0x38EEACA1AB8A6E72` (this id should be equal to the last sixteen hex characters in our fingerprint).
You can also use `gpg --fetch-key https://coreruleset.org/security.asc` directly.

### Verifying the CRS Release

Download the release file and the corresponding signature. The following example shows how to do it for `v4.0.0` release:

```bash
$ wget https://github.com/coreruleset/coreruleset/archive/refs/tags/v4.0.0.tar.gz
$ wget https://github.com/coreruleset/coreruleset/releases/download/v4.0.0/coreruleset-4.0.0.tar.gz.asc
```

**Verification**:

```bash
❯ gpg --verify coreruleset-4.0.0.tar.gz.asc v4.0.0.tar.gz
gpg: Signature made Wed Jun 30 10:05:48 2021 -03
gpg:                using RSA key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg: Good signature from "OWASP Core Rule Set <security@coreruleset.org>" [unknown]
gpg: WARNING: This key is not certified with a trusted signature!
gpg:          There is no indication that the signature belongs to the owner.
Primary key fingerprint: 3600 6F0E 0BA1 6783 2158  8211 38EE ACA1 AB8A 6E72
```

If the signature was good, the verification succeeded. If you see a warning like the above, it means you know our public key, but you are not trusting it. You can trust it by using the following method:

```bash
gpg edit-key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg> trust
Your decision: 5 (ultimate trust)
Are you sure: Yes
gpg> quit
```

Then you will see this result when verifying:
```bash
gpg --verify coreruleset-4.0.0.tar.gz.asc v4.0.0.tar.gz
gpg: Signature made Wed Jun 30 15:05:48 2021 CEST
gpg:                using RSA key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg: Good signature from "OWASP Core Rule Set <security@coreruleset.org>" [ultimate]
```

## Reporting a Vulnerability

We strive to make the OWASP CRS accessible to a wide audience of beginner and experienced users.
We welcome bug reports, false positive alert reports, evasions, usability issues, and suggestions for new detections.
Submit these types of non-vulnerability related issues via Github.
Please include your installed version and the relevant portions of your audit log.
False negative or common bypasses should [create an issue](https://github.com/coreruleset/coreruleset/issues/new) so they can be addressed.

Do this before submitting a vulnerability using our email:
1) Verify that you have the latest version of OWASP CRS.
2) Validate which Paranoia Level this bypass applies to. If it works in PL4, please send us an email.
3) If you detected anything that causes unexpected behavior of the engine via manipulation of existing CRS provided rules, please send it by email.

We also provide you with the [Sandbox project](https://coreruleset.org/docs/development/sandbox/), where you can test your bypass and report back to us. If testing using the sandbox, please include the `X-Unique-ID` from the response in your email.

Our email is [security@coreruleset.org](mailto:security@coreruleset.org). You can send us encrypted email using the same GPG key we use to sign releases, fingerprint: `3600 6F0E 0BA1 6783 2158 8211 38EE ACA1 AB8A 6E72`.

We are happy to work with the community to provide CVE identifiers for any discovered security issues if requested.

If in doubt, feel free to reach out to us!

The OWASP CRS Team.
