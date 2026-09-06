# Contributing to bunkerweb

First off all, thanks for being here and showing your support to the project !

We accept many types of contributions whether they are technical or not. Every community feedback, work or help is, and will always be, appreciated.

Before getting started, review [AGENTS.md](../AGENTS.md) for repository structure, tooling, and workflow expectations.

## Talk about the project

The first thing you can do is to talk about the project. You can share it on social media (by the way, you can can also follow us on [LinkedIn](https://www.linkedin.com/company/bunkerity/), [Twitter](https://twitter.com/bunkerity) and [GitHub](https://github.com/bunkerity)), make a blog post about it or simply tell your friends/colleagues that's an awesome project..

## Join the community

You can join the [Discord server](https://discord.com/invite/fTf46FmtyD), the [GitHub discussions](https://github.com/bunkerity/bunkerweb/discussions) and the [/r/BunkerWeb](https://www.reddit.com/r/BunkerWeb) subreddit to talk about the project and help others.

## Reporting bugs / ask for features

The preferred way to report bugs and asking for features is using [issues](https://github.com/bunkerity/bunkerweb/issues). Before opening a new one, please check if a related issue is already opened using the "filters" bar. When creating a new issue please select and fill the "Bug report" or "Feature request" template.

## Code contribution

The preferred way to contribute code is using [pull requests](https://github.com/bunkerity/bunkerweb/pulls). Before creating a pull request, please check if your code is related to an opened issue. If that's not the case, you should first create an issue so we can discuss about it. This procedure is here to avoid wasting your time in case the PR will be rejected. For minor changes (e.g. : typo, quick fix, ...), opening an issue might be facultative. **Don't forget to edit the documentations when needed !**

## Release validation

The [release workflow](workflows/release.yml) builds candidate images and Linux packages once, records their source revision and digests/checksums in `release-manifest.json`, and tests those artifacts before publication. Publishing copies the tested images without rebuilding them and verifies the package bytes. The manifest and its checksum accompany the draft release.

Release and staging runs share a queue because they use the same test infrastructure. Every required integration and platform startup check must succeed before the protected `release` environment can approve publication. That environment must retain required reviewers and keep "Prevent self-review" enabled; the workflow checks both before building and before publishing and fails closed when either is missing. A local unit or syntax check is not evidence that this release matrix has passed.

Candidate images use unique transport tags in the existing test-image repositories. Their registry and Actions artifacts follow existing retention policies; do not remove them while a release run or retry still needs them. Retrying tests or publication can reuse a candidate from the same run. Rebuilding only part of a failed candidate produces mixed receipts and is rejected; rerun the complete build set before publication. That applies only while no release exists for the tag: once the draft release has been created it is bound to the artifacts of the attempt that created it, so recover a failed publication with "Re-run failed jobs" only. "Re-run all jobs" rebuilds the artifacts and is refused because the tag is already claimed.
