# libinjection release howto

Comments and improvements welcome.

##  Update the internal version number

in `src/libinjection_sqli.c` edit the definition

```c
#define LIBINJECTION_VERSION "3.9.1"
```

## Update the CHANGELOG.md file

There isn't much of specific format. It's not GNU changelog style.  Just make sure it looks good in markdown.

## test and commit

Something like this 
```sh
make test
git commit -m 'VERSION'
```

## run ./tags.sh

This will get the version number from the file above and create a local
and remote tag.

## HELP!

I would be great to dump a src tarball on github releases.

