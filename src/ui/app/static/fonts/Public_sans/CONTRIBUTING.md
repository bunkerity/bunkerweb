# Contributing to Public Sans

We're so glad you're thinking about contributing! If you're unsure or afraid of anything, just ask or submit the issue or pull request. The worst that can happen is that you'll be politely asked to change something. We appreciate any sort of contribution, and don't want a wall of rules to get in the way of that.

Before contributing, we encourage you to read our CONTRIBUTING policy (you are here), our [LICENSE](https://github.com/uswds/public-sans/blob/master/LICENSE.md), and our [README](https://github.com/uswds/public-sans/blob/master/README.md).

## Contribution guidelines

Public Sans is a principles-driven open source typeface, maintained by the General Services Administration (GSA). We encourage contributions consistent with the project's design principles:

-   Be available as a free, open source webfont on any platform.
-   Use metrics similar to common system fonts for smoother progressive enhancement.
-   Have a broad range of weights and a good italic.
-   Perform well in headlines, text, and UI.
-   Be straightforward: have as few quirks as possible.
-   Have good multilingual support.
-   Allow for good data design with tabular figures.
-   Be strong and neutral.
-   Encourage continuous improvement — strive to be better, not necessarily perfect.

We accept pull requests that improve Public Sans and are in the service of these design principles. We review all contributions for code quality and consistency and we may reject contributions that do not meet our standards for code quality or conform to our design principles. In addition a stylistic evaluation for consistency with these design principles, we will also evaluate all contributions for the following aspects of code quality:

-   Compiles without errors
-   Passes code scanning and continuous integration tests
-   Is legible and understandable
-   Is consistent with the existing codebase

Any contributors will be responsible for updating `AUTHORS.txt` and `CONTRIBUTORS.txt` as necessary. We'll review these files as part of the code review process.

[`AUTHORS.txt`](https://github.com/uswds/public-sans/blob/master/AUTHORS.txt) is the official list of project authors for copyright purposes.

[`CONTRIBUTORS.txt`](https://github.com/uswds/public-sans/blob/master/CONTRIBUTORS.txt) is the list of people who have contributed to this project, and includes those not listed in `AUTHORS.txt` because they are not copyright authors. For example, company employees may be listed here because their company holds the copyright and is listed in `AUTHORS.txt`.

We may request changes from the author for any contributions that do not pass this evaluation. Contributions that do not pass this evaluation may be rejected. If you're unsure about anything, just ask.

## SIL Open Font License, Version 1.1

Public Sans is licensed under the [SIL Open Font License, Version 1.1](https://scripts.sil.org/cms/scripts/page.php?site_id=nrsi&id=OFL_web)

License of USWDS’s Modified Version is based on the [SIL Open Font License, Version 1.1](https://github.com/uswds/public-sans/blob/master/LICENSE.md#sil-open-font-license-version-11) section of [LICENSE.md](https://github.com/uswds/public-sans/blob/master/LICENSE.md). The terms and conditions for modifications made to the original font by USWDS in the USWDS Modified Version can be found at https://github.com/uswds/public-sans/blob/master/LICENSE.md.

By submitting a pull request, you agree to comply with the terms and conditions of the SIL Open Font License, Version 1.1. 

Public Sans is a GSA project. While GSA's contributions are not subject to copyright in the United States, contributors must license new contributions and derivative works under the SIL Open Font License, Version 1.1, as required under Section 5 of the SIL Open Font License, Version 1.1.

## Building the Font

This package has been updated to use [Python 3](https://www.python.org/downloads/) and [Docker](https://www.docker.com/get-started). You'll need to install Docker to run the build script and build the font. Docker will take care of all the Python dependencies.

### Run build
```sh
npm run build
```

## Running the specimen site locally

The specimen site runs on Jekyll and Node, powered by USWDS. The site-related files are distinct from the Public Sans source files and are kept in the following locations:

```
public-sans/
├── _data/
├── _includes/
├── _layouts/
├── _sass/
├── pages/
└── assets/
```

## Running code locally

After cloning the repo, navigate to the correct folder and install USWDS, Jekyll, and any necessary dependencies using:

```
npm start
```

Then, to run the site locally:

```
npm run serve
```

If all goes well, visit the site at http://localhost:4000.

USWDS assets are in `assets/uswds/fonts` and `assets/uswds/img`.

SASS files are kept in the `/_sass` directory. To watch for changes and recompile the styles, run:

```
npm run watch
```
