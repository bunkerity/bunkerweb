# CRS LTS Backport Policy

## Overview

This document defines the backport policy for the CRS v4.25.x Long-Term Support (LTS) release line. The goal is to provide users with a stable, secure, and predictable release they can deploy with confidence, without being forced into the rapid development cycle of the `main` branch.

Development continues on the `main` branch. The `lts/v4.25.x` branch receives only targeted backports according to this policy.

## Branch Structure

```
main              ──────────────────────────────────────► (v4.26.0-dev, v4.27.0, ...)
                         │
                         └── lts/v4.25.x  ──────────────► (v4.25.1, v4.25.2, ...)
                              (forked at v4.25.0 tag)
```

## What Is Always Backported

The following categories of changes **must** be backported to `lts/v4.25.x`:

1. **Security fixes**: Any fix for a CVE, a bypass at PL4 (security advisory), or a vulnerability in the CRS infrastructure rules (e.g., multipart parsing, request body handling). This includes fixes issued under the `xMU-YYMMDD-N` advisory format.

2. **Regression fixes**: Any fix for a regression introduced by a previous LTS point release (e.g., a backport that inadvertently changes paranoia level behavior, breaks an exclusion rule, or causes engine startup failures).

3. **Critical false positive fixes**: Fixes for false positives that affect common, widely-deployed applications at PL1, where the false positive effectively forces users to disable a rule entirely. The bar here is high: the FP must be reported by multiple independent users or reproducible with common software (e.g., WordPress, Drupal, common API frameworks).

4. **Engine compatibility fixes**: Changes required to maintain compatibility with supported ModSecurity or Coraza point releases within the LTS support window (e.g., if a ModSecurity 2.9.x or Coraza point release changes behavior that breaks an existing rule).

## What Is Never Backported

The following categories of changes **must not** be backported:

1. **New rules**: No new rule IDs are added to the LTS branch. New detection coverage belongs exclusively on `main`.

2. **New features**: No new CRS features, configuration variables, or plugin API changes.

3. **Paranoia level changes**: No moving rules between paranoia levels, no changing anomaly score weights.

4. **Rule refactoring**: No regex optimizations, no `.ra` file restructuring, no transformation chain reordering — unless required by a security fix.

5. **Toolchain and CI/CD upgrades**: No go-ftw version bumps, no Docker base image upgrades, no GitHub Actions workflow modernization — unless required for security or to maintain basic CI functionality.

6. **Test format migrations**: The LTS branch retains the test format and schema in use at the time of the fork.

7. **Cosmetic changes**: No copyright year updates (beyond what's needed for a release), no comment rewording, no whitespace cleanup.

## What Is Backported Case-by-Case

The following require a team decision (at least two core developers must approve):

1. **Non-critical false positive fixes**: FP fixes at PL1 that affect less common configurations. These are considered if the fix is low-risk (small, localized change) and the FP is well-documented.

2. **False positive fixes at PL2+**: Only if the change is trivially safe and does not alter the rule's detection scope in any meaningful way.

3. **Documentation fixes**: Updates to comments within rule files that correct factually wrong information (e.g., wrong RFC reference, wrong CAPEC tag).

4. **Data file updates**: Updates to `.data` files (e.g., adding entries to known scanner lists or restricted file extensions) are considered if the addition addresses a demonstrated gap and does not risk false positives.

## Backport Procedure

### Labeling

When a PR is merged to `main` that qualifies for backport under this policy, a core developer **must** add the GitHub label `backport:lts-4.25` to the PR before or immediately after merge.

### Cherry-pick Process

1. Cherry-picks are done one-by-one in chronological order using `git cherry-pick -x <commit-hash>` to preserve traceability.
2. If a PR has multiple commits, use the range syntax: `git cherry-pick <start>..<end>`.
3. Every cherry-pick commit message must reference the original PR number (e.g., `cherry-pick of #NNNN`).
4. If adaptation is required (e.g., version string differences, variable name changes between `main` and LTS), document the changes in the commit message.
5. The cherry-pick must pass the full LTS CI pipeline before being merged.

### Version Strings

After each backport merge, verify that `ver:'OWASP_CRS/4.25.x'` is correct in all affected rule files. The LTS branch must never reference a `main`-track version.

### Testing

Every backport PR to `lts/v4.25.x` must:

- Pass the full regression test suite on the LTS branch.
- Include any new or modified test cases from the original PR, adapted if necessary for the LTS test format.
- Be reviewed by at least one core developer who did **not** author the cherry-pick.

## Release Cadence

LTS point releases (v4.25.1, v4.25.2, ...) are published on a **quarterly** schedule, unless a security fix demands an out-of-band release.

- **Quarterly releases**: Batch all accumulated backports. Announce via the standard channels (blog post, mailing list, Twitter/X).
- **Out-of-band releases**: Security-only. Published as soon as the fix is ready and tested. Announced with a security advisory.

## End of Life

The CRS v4.25.x LTS release line will receive security fixes until **Q3 2027: 1.5 years from v4.25.0 release]**. After the EOL date:

- No further releases will be made from the `lts/v4.25.x` branch.
- The branch will be preserved read-only for historical reference.
- Users will be directed to upgrade to the current stable or a newer LTS release.

The EOL date is published in `SECURITY.md` on both `main` and `lts/v4.25.x`.

## Decision Authority

Backport decisions that fall under "always" or "never" categories do not require team discussion. Case-by-case decisions require approval from at least two core developers. Disputes are resolved by the project co-leads.

## References

- [CRS Release Procedure](https://github.com/coreruleset/coreruleset/wiki/Release-Procedure)
- [CRS Security Policy](https://github.com/coreruleset/coreruleset/blob/main/SECURITY.md)
- [CRS Contribution Guidelines](https://github.com/coreruleset/coreruleset/blob/main/CONTRIBUTING.md)
