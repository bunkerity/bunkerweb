#!/usr/bin/env perl

use strict;
use warnings;

use Cwd qw( abs_path );
use FindBin qw( $Bin );

eval <<'EOF';
use Test::More 0.88;
use File::Temp qw( tempdir );
use IPC::Run3 qw( run3 );
EOF

if ($@) {
    print
        "1..0 # skip decoder limit override tests need Test::More 0.88, File::Temp, and IPC::Run3\n";
    exit 0;
}

my $root        = abs_path("$Bin/..");
my $include_dir = "$root/include";
my $src_dir     = "$root/src";
my $cc          = $ENV{CC} || 'cc';

# The checks below rebuild the library with -Werror. Only gcc and clang are
# known to compile it cleanly with the flags used here, so skip elsewhere
# instead of failing on a missing compiler or an unrelated warning.
my ( $cc_version, $cc_stderr ) = ( q{}, q{} );
my $cc_status = eval {
    run3( [ $cc, '--version' ], \undef, \$cc_version, \$cc_stderr );
    $?;
};
$cc_version .= $cc_stderr;
if ( !defined $cc_status
    || $cc_status != 0
    || $cc_version !~ /gcc|clang|Free Software Foundation/ ) {
    plan( skip_all => "decoder limit override tests need gcc or clang" );
}

# Keep instrumentation such as -fsanitize=address from the environment, but
# not its warning flags. Those vary by CI job and would trip -Werror below.
my @instrumentation = grep { /^-f/ }
    map { split ' ' } grep { defined } @ENV{ 'CFLAGS', 'LDFLAGS' };

my @base = (
    $cc,
    @instrumentation,
    '-std=c99',
    '-Wall',
    '-Wextra',
    '-Werror',
    '-Wno-unused-function',
    '-Wno-unused-parameter',
    '-DPACKAGE_VERSION="test"',
    "-I$include_dir",
    "-I$src_dir",
);

for my $definition (
    '-DMAXIMUM_DATA_STRUCTURE_DEPTH=1000',
    '-DMAXIMUM_DATA_STRUCTURE_VALUES=1000000',
) {
    my ( $status, $stderr ) = _run(
        @base,
        $definition,
        '-fsyntax-only',
        "$src_dir/maxminddb.c",
    );
    is( $status, 0, "$definition compiles without warnings" )
        or diag($stderr);
}

for my $definition (
    '-DMAXIMUM_DATA_STRUCTURE_DEPTH=0',
    '-DMAXIMUM_DATA_STRUCTURE_DEPTH=-1',
    '-DMAXIMUM_DATA_STRUCTURE_VALUES=0',
    '-DMAXIMUM_DATA_STRUCTURE_VALUES=-1',
    '-DMAXIMUM_DATA_STRUCTURE_BYTES=0',
    '-DMAXIMUM_DATA_STRUCTURE_BYTES=-1',
) {
    my ( $status, $stderr ) = _run(
        @base,
        $definition,
        '-fsyntax-only',
        "$src_dir/maxminddb.c",
    );
    isnt( $status, 0, "$definition is rejected" );
    like(
        $stderr,
        qr/MAXIMUM_DATA_STRUCTURE_\w+ must be/,
        "$definition explains its range"
    );
}

my $tempdir = tempdir( CLEANUP => 1 );
my $source  = "$tempdir/override.c";
open my $fh, '>', $source or die $!;
print {$fh} <<'EOF' or die $!;
#include <maxminddb.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static int fail(const char *path, const char *what, int status, int code) {
    fprintf(stderr, "%s: %s: %s\n", path, what, MMDB_strerror(status));
    return code;
}

static int lookup(const char *path, const char *address, MMDB_s *mmdb,
                  MMDB_lookup_result_s *result) {
    int status = MMDB_open(path, MMDB_MODE_MMAP, mmdb);
    if (status != MMDB_SUCCESS) {
        return fail(path, "open", status, 1);
    }
    int gai_error, mmdb_error;
    *result = MMDB_lookup_string(mmdb, address, &gai_error, &mmdb_error);
    if (gai_error != 0 || mmdb_error != MMDB_SUCCESS || !result->found_entry) {
        MMDB_close(mmdb);
        return fail(path, "lookup found no entry", mmdb_error, 2);
    }
    return 0;
}

static int decode(const char *path, size_t expected_count) {
    MMDB_s mmdb;
    MMDB_lookup_result_s result;
    int code = lookup(path, "1.1.1.1", &mmdb, &result);
    if (code != 0) {
        return code;
    }
    MMDB_entry_data_list_s *list = NULL;
    int status = MMDB_get_entry_data_list(&result.entry, &list);
    if (status != MMDB_SUCCESS) {
        MMDB_close(&mmdb);
        return fail(path, "full decode", status, 3);
    }
    size_t count = 0;
    for (MMDB_entry_data_list_s *node = list; node; node = node->next) {
        count++;
    }
    MMDB_free_entry_data_list(list);
    MMDB_close(&mmdb);
    if (count != expected_count) {
        fprintf(stderr, "%s: decoded %zu values, expected %zu\n", path, count,
                expected_count);
        return 4;
    }
    return 0;
}

static int
check_status(const char *path, const char *address, int expected_status) {
    MMDB_s mmdb;
    MMDB_lookup_result_s result;
    int code = lookup(path, address, &mmdb, &result);
    if (code != 0) {
        return code;
    }
    MMDB_entry_data_list_s *list = NULL;
    int status = MMDB_get_entry_data_list(&result.entry, &list);
    MMDB_free_entry_data_list(list);
    MMDB_close(&mmdb);
    if (status != expected_status) {
        return fail(path, "full decode returned an unexpected status", status,
                    7);
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 3 && strcmp(argv[1], "--accept") == 0) {
        return check_status(argv[2], "1.2.3.4", MMDB_SUCCESS);
    }
    if (argc == 2) {
        return check_status(
            argv[1], "1.1.1.1", MMDB_DECODER_LIMIT_ERROR);
    }
    if (argc != 3) {
        return 5;
    }
    int status = decode(argv[1], 65537);
    return status == 0 ? decode(argv[2], 34) : status;
}
EOF
close $fh or die $!;

# Each override rebuilds the library with the given definitions, then runs the
# program above. Two fixtures means decode both and check the value counts;
# one fixture means expect MMDB_DECODER_LIMIT_ERROR.
my @overrides = (
    {
        desc        => 'limits one above the defaults',
        definitions => [
            '-DMAXIMUM_DATA_STRUCTURE_VALUES=65537',
            '-DMAXIMUM_DATA_STRUCTURE_BYTES=2097153',
        ],
        fixtures => [
            'MaxMind-DB-test-decoder-value-limit-over.mmdb',
            'MaxMind-DB-test-decoder-payload-limit-over.mmdb',
        ],
    },
    {
        desc        => 'a 2 GiB payload limit',
        definitions => ['-DMAXIMUM_DATA_STRUCTURE_BYTES=2147483648'],
        fixtures    =>
            ['MaxMind-DB-test-payload-amplification-dos-worst-case.mmdb'],
    },
    {
        # The fixture's first value is 65,535 bytes, one more than the limit,
        # so the single-value check rejects it before any total accumulates.
        desc        => 'a payload limit below a single value',
        definitions => ['-DMAXIMUM_DATA_STRUCTURE_BYTES=65534'],
        fixtures    => ['MaxMind-DB-test-payload-amplification-dos.mmdb'],
    },
    {
        desc        => 'a raised nesting depth limit',
        definitions => ['-DMAXIMUM_DATA_STRUCTURE_DEPTH=1000'],
        accept      => 1,
        fixtures    => [
            '../bad-data/libmaxminddb/libmaxminddb-deep-array-nesting.mmdb'
        ],
    },
);

my $count = 0;
for my $override (@overrides) {
    my $executable = "$tempdir/override-" . $count++;
    my ( $compile_status, $compile_stderr ) = _run(
        @base,
        @{ $override->{definitions} },
        "$src_dir/maxminddb.c",
        "$src_dir/data-pool.c",
        $source,
        '-lm',
        '-o',
        $executable,
    );
    is( $compile_status, 0, "$override->{desc} compiles and links" )
        or diag($compile_stderr);
    next if $compile_status != 0;

    my @arguments =
        map { "$Bin/maxmind-db/test-data/$_" } @{ $override->{fixtures} };
    unshift @arguments, '--accept' if $override->{accept};
    my ( $status, $stderr ) = _run( $executable, @arguments );
    is( $status, 0, "$override->{desc} takes effect at runtime" )
        or diag($stderr);
}

done_testing();

sub _run {
    my @command = @_;
    my ( $stdout, $stderr );
    run3( \@command, \undef, \$stdout, \$stderr );
    my $wait = $?;

    # A child killed by a signal has no exit code, so report the signal as a
    # failure instead of letting $? >> 8 read as success.
    if ( $wait & 127 ) {
        my $signal = $wait & 127;
        return ( 128 + $signal, "$stderr\nkilled by signal $signal\n" );
    }
    return ( $wait >> 8, $stderr );
}
