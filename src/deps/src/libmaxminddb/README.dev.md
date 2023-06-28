# Releasing this library

We release by uploading the tarball to GitHub and uploading Ubuntu PPAs.

## Creating the release tarball
You may want to refer to the section about prerequisites.

* Check whether there are any open issues to fix while you're doing this.
* Update `Changes.md` to include specify the new version, today's date, and
  list relevant changes. Commit this.
* Create a new branch off of the latest `main` for the release.
* Run `./dev-bin/release.sh` to update various files in the distro, our
  GitHub pages, and creates a GitHub release with the tarball.
* Check the release looks good on both GitHub and launchpad.net.
* Make a pull request against `main` with the changes from the release
  script.

## PPA

In order to upload a PPA, you have to create a launchpad.net account and
register a GPG key with that account. You also need to be added to the MaxMind
team. Ask in the dev channel for someone to add you. See
https://help.launchpad.net/Packaging/PPA for more details.

The PPA release script is at `dev-bin/ppa-release.sh`. Running it should
guide you though the release, although it may require some changes to run on
configurations different than Greg's machine.

Check whether any new Ubuntu versions need to be listed in this script
before running it.

You should run it from `main`.

## Homebrew (optional)

Releasing to Homebrew is no longer required as the formulas are easily
updated by the end-user using a built-in feature in the tool. These
directions remain in case there is a more significant change to the
build process that may require a non-trivial update to the formula or
in the case where we want the Homebrew version updated promptly for
some reason.

* Go to https://github.com/Homebrew/homebrew-core/edit/master/Formula/libmaxminddb.rb
* Edit the file to update the url and sha256. You can get the sha256 for the
  tarball with the `sha256sum` command line utility.
* Make a commit with the summary `libmaxminddb <VERSION>`
* Submit a PR with the changes you just made.

# Prerequisites for releasing

* Required packages (Ubuntu Artful): vim git-core dput build-essential
  autoconf automake libtool git-buildpackage libfile-slurp-perl pandoc
  dirmngr libfile-slurp-tiny-perl libdatetime-perl debhelper dh-autoreconf
  libipc-run3-perl libtest-output-perl devscripts
* Install [gh](https://github.com/cli/cli/releases).
* GitHub ssh key (e.g. in `~/.ssh/id_rsa`)
* Git config (e.g. `~/.gitconfig`)
* Import your GPG secret key (or create one if you don't have a suitable
  one)
  * `gpg --import /path/to/key`
  * `gpg --edit-key KEYID` and trust it ultimately
  * Ensure it shows with `gpg --list-secret-keys`
* You need to be invited to the launchpad.net MaxMind organization on your
  launchpad.net account.
* You need your GPG key listed on your launchpad.net account
  * You can add it in the web interface. It wants the output of
    `gpg --fingerprint`.
  * Part of the instructions involve having your key published on the
    Ubuntu keyserver:
    `gpg --keyserver keyserver.ubuntu.com --send-keys KEYID`
  * You'll get an email with an encrypted payload that you need to decrypt
    and follow the link to confirm it.
* Ensure `dch` knows your name and email. Refer to its man page for how to
  tell it this. One way is to set the `DEBFULLNAME` and `DEBEMAIL`
  environment variables. These should match your GPG key's name and email
  exactly. This is what gets used in the Debian changelog as well as
  defines what GPG key to use.
