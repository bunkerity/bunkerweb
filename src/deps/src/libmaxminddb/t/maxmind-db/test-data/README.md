The write-test-dbs script will create a small set of test databases with a
variety of data and record sizes (24, 28, & 32 bit).

These test databases are useful for testing code that reads MaxMind DB files.

There is also a `maps-with-pointers.raw` file. This contains the raw output of
the MaxMind::DB::Writer::Serializer module, when given a series of maps which
share some keys and values. It is used to test that decoder code can handle
pointers to map keys and values, as well as to the whole map.

There are several ways to figure out what IP addresses are actually in the
test databases. You can take a look at the
[souce-data directory](https://github.com/maxmind/MaxMind-DB/tree/master/source-data)
in this repository. This directory contains JSON files which are used to
generate many (but not all) of the database files.

You can also use the
[mmdb-dump-database script](https://github.com/maxmind/MaxMind-DB-Reader-perl/blob/master/eg/mmdb-dump-database)
in the
[MaxMind-DB-Reader-perl repository](https://github.com/maxmind/MaxMind-DB-Reader-perl).

Some databases are intentionally broken and cannot be dumped. You can look at
the
[script which generates these databases](https://github.com/maxmind/MaxMind-DB/blob/master/test-data/write-test-data.pl)
to see what IP addresses they include, which will be necessary for those
databases which cannot be dumped because they contain intentional errors.
