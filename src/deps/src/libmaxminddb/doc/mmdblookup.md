# NAME

mmdblookup - a utility to look up an IP address in a MaxMind DB file

# SYNOPSIS

mmdblookup --file [FILE PATH] --ip [IP ADDRESS] [DATA PATH]

# DESCRIPTION

`mmdblookup` looks up an IP address in the specified MaxMind DB file. The
record for the IP address is displayed with `{}` to denote maps and `[]` to
denote arrays. The values are followed by type annotations. This output is
_not_ JSON and is not intended to be used as such. If you need JSON, please
see [`mmdbinspect`](https://github.com/maxmind/mmdbinspect).

If an IP's data entry resolves to a map or array, you can provide a lookup
path to only show part of that data.

For example, given a JSON structure like this:

```js
{
    "names": {
        "en": "Germany",
        "de": "Deutschland"
    },
    "cities": [ "Berlin", "Frankfurt" ]
}
```

You could look up just the English name by calling mmdblookup with a lookup
path of:

```bash
mmdblookup --file ... --ip ... names en
```

Or you could look up the second city in the list with:

```bash
mmdblookup --file ... --ip ... cities 1
```

Array numbering begins with zero (0).

If you do not provide a path to lookup, all of the information for a given IP
will be shown.

# OPTIONS

This application accepts the following options:

-f, --file

:    The path to the MMDB file. Required.

-i, --ip

:    The IP address to look up. Required.

-v, --verbose

:    Turns on verbose output. Specifically, this causes this
     application to output the database metadata.

--version

:    Print the program's version number and exit.

-h, -?, --help

:    Show usage information.

# BUG REPORTS AND PULL REQUESTS

Please report all issues to
[our GitHub issue tracker](https://github.com/maxmind/libmaxminddb/issues). We
welcome bug reports and pull requests. Please note that pull requests are
greatly preferred over patches.

# AUTHORS

This utility was written by Boris Zentner (bzentner@maxmind.com) and Dave
Rolsky (drolsky@maxmind.com).

# COPYRIGHT AND LICENSE

Copyright 2013-2025 MaxMind, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

# SEE ALSO

libmaxminddb(3)
