---
layout: default
title: MaxMind DB File Format Specification
version: v2.0
---
# MaxMind DB File Format Specification

## Description

The MaxMind DB file format is a database format that maps IPv4 and IPv6
addresses to data records using an efficient binary search tree.

## Version

This spec documents **version 2.0** of the MaxMind DB binary format.

The version number consists of separate major and minor version numbers. It
should not be considered a decimal number. In other words, version 2.10 comes
after version 2.9.

Code which is capable of reading a given major version of the format should
not be broken by minor version changes to the format.

## Overview

The binary database is split into three parts:

1. The binary search tree. Each level of the tree corresponds to a single bit
in the 128 bit representation of an IPv6 address.
2. The data section. These are the values returned to the client for a
specific IP address, e.g. "US", "New York", or a more complex map type made up
of multiple fields.
3. Database metadata. Information about the database itself.

## Database Metadata

This portion of the database is stored at the end of the file. It is
documented first because understanding some of the metadata is key to
understanding how the other sections work.

This section can be found by looking for a binary sequence matching
"\xab\xcd\xefMaxMind.com". The *last* occurrence of this string in the file
marks the end of the data section and the beginning of the metadata. Since we
allow for arbitrary binary data in the data section, some other piece of data
could contain these values. This is why you need to find the last occurrence
of this sequence.

The maximum allowable size for the metadata section, including the marker that
starts the metadata, is 128kb.

The metadata is stored as a map data structure. This structure is described
later in the spec. Changing a key's data type or removing a key would
consistute a major version change for this spec.

Except where otherwise specified, each key listed is required for the database
to be considered valid.

Adding a key constitutes a minor version change. Removing a key or changing
its type constitutes a major version change.

The list of known keys for the current version of the format is as follows:

### node\_count

This is an unsigned 32-bit integer indicating the number of nodes in the
search tree.

### record\_size

This is an unsigned 16-bit integer. It indicates the number of bits in a
record in the search tree. Note that each node consists of *two* records.

### ip\_version

This is an unsigned 16-bit integer which is always 4 or 6. It indicates
whether the database contains IPv4 or IPv6 address data.

### database\_type

This is a string that indicates the structure of each data record associated
with an IP address. The actual definition of these structures is left up to
the database creator.

Names starting with "GeoIP" are reserved for use by MaxMind (and "GeoIP" is a
trademark anyway).

### languages

An array of strings, each of which is a locale code. A given record may
contain data items that have been localized to some or all of these
locales. Records should not contain localized data for locales not included in
this array.

This is an optional key, as this may not be relevant for all types of data.

### binary\_format\_major\_version

This is an unsigned 16-bit integer indicating the major version number for the
database's binary format.

### binary\_format\_minor\_version

This is an unsigned 16-bit integer indicating the minor version number for the
database's binary format.

### build\_epoch

This is an unsigned 64-bit integer that contains the database build timestamp
as a Unix epoch value.

### description

This key will always point to a map. The keys of that map will be language
codes, and the values will be a description in that language as a UTF-8
string.

The codes may include additional information such as script or country
identifiers, like "zh-TW" or "mn-Cyrl-MN". The additional identifiers will be
separated by a dash character ("-").

This key is optional. However, creators of databases are strongly
encouraged to include a description in at least one language.

### Calculating the Search Tree Section Size

The formula for calculating the search tree section size *in bytes* is as
follows:

    ( ( $record_size * 2 ) / 8 ) * $number_of_nodes

The end of the search tree marks the beginning of the data section.

## Binary Search Tree Section

The database file starts with a binary search tree. The number of nodes in the
tree is dependent on how many unique netblocks are needed for the particular
database. For example, the city database needs many more small netblocks than
the country database.

The top most node is always located at the beginning of the search tree
section's address space. The top node is node 0.

Each node consists of two records, each of which is a pointer to an address in
the file.

The pointers can point to one of three things. First, it may point to another
node in the search tree address space. These pointers are followed as part of
the IP address search algorithm, described below.

The pointer can point to a value equal to `$number_of_nodes`. If this is the
case, it means that the IP address we are searching for is not in the
database.

Finally, it may point to an address in the data section. This is the data
relevant to the given netblock.

### Node Layout

Each node in the search tree consists of two records, each of which is a
pointer. The record size varies by database, but inside a single database node
records are always the same size. A record may be anywhere from 24 to 128 bits
long, dependending on the number of nodes in the tree. These pointers are
stored in big-endian format (most significant byte first).

Here are some examples of how the records are laid out in a node for 24, 28,
and 32 bit records. Larger record sizes follow this same pattern.

#### 24 bits (small database), one node is 6 bytes

    | <------------- node --------------->|
    | 23 .. 0          |          23 .. 0 |

#### 28 bits (medium database), one node is 7 bytes

    | <------------- node --------------->|
    | 23 .. 0 | 27..24 | 27..24 | 23 .. 0 |

Note, the last 4 bits of each pointer are combined into the middle byte.

#### 32 bits (large database), one node is 8 bytes

    | <------------- node --------------->|
    | 31 .. 0          |          31 .. 0 |

### Search Lookup Algorithm

The first step is to convert the IP address to its big-endian binary
representation. For an IPv4 address, this becomes 32 bits. For IPv6 you get
128 bits.

The leftmost bit corresponds to the first node in the search tree. For each
bit, a value of 0 means we choose the left record in a node, and a value of 1
means we choose the right record.

The record value is always interpreted as an unsigned integer. The maximum
size of the integer is dependent on the number of bits in a record (24, 28, or
32).

If the record value is a number that is less than the *number of nodes* (not
in bytes, but the actual node count) in the search tree (this is stored in the
database metadata), then the value is a node number. In this case, we find
that node in the search tree and repeat the lookup algorithm from there.

If the record value is equal to the number of nodes, that means that we do not
have any data for the IP address, and the search ends here.

If the record value is *greater* than the number of nodes in the search tree,
then it is an actual pointer value pointing into the data section. The value
of the pointer is calculated from the start of the data section, *not* from
the start of the file.

In order to determine where in the data section we should start looking, we use
the following formula:

    $data_section_offset = ( $record_value - $node_count ) - 16

The `16` is the size of the data section separator (see below for details).

The reason that we subtract the `$node_count` is best demonstrated by an example.

Let's assume we have a 24-bit tree with 1,000 nodes. Each node contains 48
bits, or 6 bytes. The size of the tree is 6,000 bytes.

When a record in the tree contains a number that is < 1,000, this is a *node
number*, and we look up that node. If a record contains a value >= 1,016, we
know that it is a data section value. We subtract the node count (1,000) and
then subtract 16 for the data section separator, giving us the number 0, the
first byte of the data section.

If a record contained the value 6,000, this formula would give us an offset of
4,984 into the data section.

In order to determine where in the file this offset really points to, we also
need to know where the data section starts. This can be calculated by
determining the size of the search tree in bytes and then adding an additional
16 bytes for the data section separator.

So the final formula to determine the offset in the file is:

    $offset_in_file = ( $record_value - $node_count )
                      + $search_tree_size_in_bytes

### IPv4 addresses in an IPv6 tree

When storing IPv4 addresses in an IPv6 tree, they are stored as-is, so they
occupy the first 32-bits of the address space (from 0 to 2**32 - 1).

Creators of databases should decide on a strategy for handling the various
mappings between IPv4 and IPv6.

The strategy that MaxMind uses for its GeoIP databases is to include a pointer
from the `::ffff:0:0/96` subnet to the root node of the IPv4 address space in
the tree. This accounts for the
[IPv4-mapped IPv6 address](http://en.wikipedia.org/wiki/IPv6#IPv4-mapped_IPv6_addresses).

MaxMind also includes a pointer from the `2002::/16` subnet to the root node
of the IPv4 address space in the tree. This accounts for the
[6to4 mapping](http://en.wikipedia.org/wiki/6to4) subnet.

Database creators are encouraged to document whether they are doing something
similar for their databases.

The Teredo subnet cannot be accounted for in the tree. Instead, code that
searches the tree can offer to decode the IPv4 portion of a Teredo address and
look that up.

## Data Section Separator

There are 16 bytes of NULLs in between the search tree and the data
section. This separator exists in order to make it possible for a verification
tool to distinguish between the two sections.

This separator is not considered part of the data section itself. In other
words, the data section starts at `$size\_of\_search_tree + 16" bytes in the
file.

## Output Data Section

Each output data field has an associated type, and that type is encoded as a
number that begins the data field. Some types are variable length. In those
cases, the type indicator is also followed by a length. The data payload
always comes at the end of the field.

All binary data is stored in big-endian format.

Note that the *interpretation* of a given data type's meaning is decided by
higher-level APIs, not by the binary format itself.

### pointer - 1

A pointer to another part of the data section's address space. The pointer
will point to the beginning of a field. It is illegal for a pointer to point
to another pointer.

Pointer values start from the beginning of the data section, *not* the
beginning of the file.

### UTF-8 string - 2

A variable length byte sequence that contains valid utf8. If the length is
zero then this is an empty string.

### double - 3

This is stored as an IEEE-754 double (binary64) in big-endian format. The
length of a double is always 8 bytes.

### bytes - 4

A variable length byte sequence containing any sort of binary data. If the
length is zero then this a zero-length byte sequence.

This is not currently used but may be used in the future to embed non-text
data (images, etc.).

### integer formats

Integers are stored in variable length binary fields.

We support 16-bit, 32-bit, 64-bit, and 128-bit unsigned integers. We also
support 32-bit signed integers.

A 128-bit integer can use up to 16 bytes, but may use fewer. Similarly, a
32-bit integer may use from 0-4 bytes. The number of bytes used is determined
by the length specifier in the control byte. See below for details.

A length of zero always indicates the number 0.

When storing a signed integer, the left-most bit is the sign. A 1 is negative
and a 0 is positive.

The type numbers for our integer types are:

* unsigned 16-bit int - 5
* unsigned 32-bit int - 6
* signed 32-bit int - 8
* unsigned 64-bit int - 9
* unsigned 128-bit int - 10

The unsigned 32-bit and 128-bit types may be used to store IPv4 and IPv6
addresses, respectively.

The signed 32-bit integers are stored using the 2's complement representation.

### map - 7

A map data type contains a set of key/value pairs. Unlike other data types,
the length information for maps indicates how many key/value pairs it
contains, not its length in bytes. This size can be zero.

See below for the algorithm used to determine the number of pairs in the
hash. This algorithm is also used to determine the length of a field's
payload.

### array - 11

An array type contains a set of ordered values. The length information for
arrays indicates how many values it contains, not its length in bytes. This
size can be zero.

This type uses the same algorithm as maps for determining the length of a
field's payload.

### data cache container - 12

This is a special data type that marks a container used to cache repeated
data. For example, instead of repeating the string "United States" over and
over in the database, we store it in the cache container and use pointers
*into* this container instead.

Nothing in the database will ever contain a pointer to the this field
itself. Instead, various fields will point into the container.

The primary reason for making this a separate data type versus simply inlining
the cached data is so that a database dumper tool can skip this cache when
dumping the data section. The cache contents will end up being dumped as
pointers into it are followed.

### end marker - 13

The end marker marks the end of the data section. It is not strictly
necessary, but including this marker allows a data section deserializer to
process a stream of input, rather than having to find the end of the section
before beginning the deserialization.

This data type is not followed by a payload, and its size is always zero.

### boolean - 14

A true or false value. The length information for a boolean type will always
be 0 or 1, indicating the value. There is no payload for this field.

### float - 15

This is stored as an IEEE-754 float (binary32) in big-endian format. The
length of a float is always 4 bytes.

This type is provided primarily for completeness. Because of the way floating
point numbers are stored, this type can easily lose precision when serialized
and then deserialized. If this is an issue for you, consider using a double
instead.

### Data Field Format

Each field starts with a control byte. This control byte provides information
about the field's data type and payload size.

The first three bits of the control byte tell you what type the field is. If
these bits are all 0, then this is an "extended" type, which means that the
*next* byte contains the actual type. Otherwise, the first three bits will
contain a number from 1 to 7, the actual type for the field.

We've tried to assign the most commonly used types as numbers 1-7 as an
optimization.

With an extended type, the type number in the second byte is the number minus
7. In other words, an array (type 11) will be stored with a 0 for the type in
the first byte and a 4 in the second.

Here is an example of how the control byte may combine with the next byte to
tell us the type:

    001XXXXX          pointer
    010XXXXX          UTF-8 string
    010XXXXX          unsigned 32-bit int (ASCII)
    000XXXXX 00000011 unsigned 128-bit int (binary)
    000XXXXX 00000100 array
    000XXXXX 00000110 end marker

#### Payload Size

The next five bits in the control byte tell you how long the data field's
payload is, except for maps and pointers. Maps and pointers use this size
information a bit differently. See below.

If the five bits are smaller than 29, then those bits are the payload size in
bytes. For example:

    01000010          UTF-8 string - 2 bytes long
    01011100          UTF-8 string - 28 bytes long
    11000001          unsigned 32-bit int - 1 byte long
    00000011 00000011 unsigned 128-bit int - 3 bytes long

If the five bits are equal to 29, 30, or 31, then use the following algorithm
to calculate the payload size.

If the value is 29, then the size is 29 + *the next byte after the type
specifying bytes as an unsigned integer*.

If the value is 30, then the size is 285 + *the next two bytes after the type
specifying bytes as a single unsigned integer*.

If the value is 31, then the size is 65,821 + *the next three bytes after the
type specifying bytes as a single unsigned integer*.

Some examples:

    01011101 00110011 UTF-8 string - 80 bytes long

In this case, the last five bits of the control byte equal 29. We treat the
next byte as an unsigned integer. The next byte is 51, so the total size is
(29 + 51) = 80.

    01011110 00110011 00110011 UTF-8 string - 13,392 bytes long

The last five bits of the control byte equal 30. We treat the next two bytes
as a single unsigned integer. The next two bytes equal 13,107, so the total
size is (285 + 13,107) = 13,392.

    01011111 00110011 00110011 00110011 UTF-8 string - 3,421,264 bytes long

The last five bits of the control byte equal 31. We treat the next three bytes
as a single unsigned integer. The next three bytes equal 3,355,443, so the
total size is (65,821 + 3,355,443) = 3,421,264.

This means that the maximum payload size for a single field is 16,843,036
bytes.

The binary number types always have a known size, but for consistency's sake,
the control byte will always specify the correct size for these types.

#### Maps

Maps use the size in the control byte (and any following bytes) to indicate
the number of key/value pairs in the map, not the size of the payload in
bytes.

This means that the maximum number of pairs for a single map is 16,843,036.

Maps are laid out with each key followed by its value, followed by the next
pair, etc.

The keys are **always** UTF-8 strings. The values may be any data type,
including maps or pointers.

Once we know the number of pairs, we can look at each pair in turn to
determine the size of the key and the key name, as well as the value's type
and payload.

#### Pointers

Pointers use the last five bits in the control byte to calculate the pointer
value.

To calculate the pointer value, we start by subdiving the five bits into two
groups. The first two bits indicate the size, and the next three bits are part
of the value, so we end up with a control byte breaking down like this:
001SSVVV.

The size can be 0, 1, 2, or 3.

If the size is 0, the pointer is built by appending the next byte to the last
three bits to produce an 11-bit value.

If the size is 1, the pointer is built by appending the next two bytes to the
last three bits to produce a 19-bit value + 2048.

If the size is 2, the pointer is built by appending the next three bytes to the
last three bits to produce a 27-bit value + 526336.

Finally, if the size is 3, the pointer's value is contained in the next four
bytes as a 32-bit value. In this case, the last three bits of the control byte
are ignored.

This means that we are limited to 4GB of address space for pointers, so the
data section size for the database is limited to 4GB.

## Reference Implementations

### Writer

* [Perl](https://github.com/maxmind/MaxMind-DB-Writer-perl)

### Reader

* [C](https://github.com/maxmind/libmaxminddb)
* [C#](https://github.com/maxmind/MaxMind-DB-Reader-dotnet)
* [Java](https://github.com/maxmind/MaxMind-DB-Reader-java)
* [Perl](https://github.com/maxmind/MaxMind-DB-Reader-perl)
* [PHP](https://github.com/maxmind/MaxMind-DB-Reader-php)
* [Python](https://github.com/maxmind/MaxMind-DB-Reader-python)

## Authors

This specification was created by the following authors:

* Greg Oschwald \<goschwald@maxmind.com\>
* Dave Rolsky \<drolsky@maxmind.com\>
* Boris Zentner \<bzentner@maxmind.com\>

## License

This work is licensed under the Creative Commons Attribution-ShareAlike 3.0
Unported License. To view a copy of this license, visit
[http://creativecommons.org/licenses/by-sa/3.0/](http://creativecommons.org/licenses/by-sa/3.0/)
or send a letter to Creative Commons, 444 Castro Street, Suite 900, Mountain
View, California, 94041, USA

