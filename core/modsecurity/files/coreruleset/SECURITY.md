# Security Policy

## Supported Versions

OWASP CRS has two types of releases, Major releases (3.0.0, 3.1.0, 3.2.0 etc.) and point releases (3.0.1, 3.0.2 etc.).
For more information see our [wiki](https://github.com/SpiderLabs/owasp-modsecurity-crs/wiki/Release-Policy).
The OWASP CRS officially supports the two point releases with security patching preceding the current major release .
We are happy to receive and merge PR's that address security issues in older versions of the project, but the team itself may choose not to fix these.
Along those lines, OWASP CRS team may not issue security notifications for unsupported software.

| Version   | Supported          |
| --------- | ------------------ |
| 3.3.x-dev | :white_check_mark: |
| 3.2.x     | :white_check_mark: |
| 3.1.x     | :white_check_mark: |
| 3.0.x     | :x:                |

## Reporting a Vulnerability

We strive to make the OWASP ModSecurity CRS accessible to a wide audience of beginner and experienced users.
We welcome bug reports, false positive alert reports, evasions, usability issues, and suggestions for new detections.
Submit these types of non-vulnerability related issues via Github.
Please include your installed version and the relevant portions of your audit log.
False negative or common bypasses should [create an issue](https://github.com/SpiderLabs/owasp-modsecurity-crs/issues/new) so they can be addressed.

Do this before submitting a vulnerability using our email:
1) Verify that you have the latest version of OWASP CRS.
2) Validate which Paranoia Level this bypass applies to. If it works in PL4, please send us an email.
3) If you detected anything that causes unexpected behavior of the engine via manipulation of existing CRS provided rules, please send it by email.

Our email is [security@coreruleset.org](mailto:security@coreruleset.org). You can send us encrypted email using [this key](https://coreruleset.org/security.asc), (fingerprint: `3600 6F0E 0BA1 6783 2158 8211 38EE ACA1 AB8A 6E72`).

We are happy to work with the community to provide CVE identifiers for any discovered security issues if requested.

If in doubt, feel free to reach out to us!
