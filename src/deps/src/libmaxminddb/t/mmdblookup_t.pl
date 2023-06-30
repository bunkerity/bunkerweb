#!/usr/bin/env perl

use strict;
use warnings;

use FindBin qw( $Bin );

eval <<'EOF';
use Test::More 0.88;
use IPC::Run3 qw( run3 );
EOF

if ($@) {
    print
        "1..0 # skip all tests skipped - these tests need the Test::More 0.88, IPC::Run3 and Test::Output modules:\n";
    print "$@";
    exit 0;
}

my $mmdblookup    = "$Bin/../bin/mmdblookup";
my $test_data_dir = "$Bin/maxmind-db/test-data";

{
    ok( -x $mmdblookup, 'mmdblookup script is executable' );
}

for my $arg (qw( -h -? --help )) {
    _test_stdout(
        [$arg],
        qr{mmdblookup --file.+This application accepts the following options:}s,
        0,
        "help output from $arg"
    );
}

_test_both(
    [],
    qr{mmdblookup --file.+This application accepts the following options:}s,
    qr{ERROR: You must provide a filename with --file},
    1,
    "help output with no CLI options"
);

_test_stderr(
    [qw( --file foo )],
    qr{ERROR: You must provide an IP address with --ip},
    1,
    'error when no --ip is given'
);

_test_stdout(
    [qw( --version )],
    qr/mmdblookup version \d+\.\d+\.\d+/,
    0,
    'output for --version'
);

_test_stdout(
    ['--file', "$test_data_dir/GeoIP2-City-Test.mmdb", '--ip', '2.125.160.216'],
    qr/"en"\s*:\s*"Boxford"/,
    0,
    'output for 2.125.160.216'
);

_test_stdout(
    ['--file', "$test_data_dir/GeoIP2-City-Test.mmdb", '--ip', '2.125.160.216', '--verbose'],
    qr/Database metadata.+"en"\s*:\s*"Boxford"/s,
    0,
    'verbose output for 2.125.160.216'
);

_test_stdout(
    ['--file', "$test_data_dir/GeoIP2-City-Test.mmdb", '--ip', '2.125.160.216', qw( location latitude )],
    qr/^\s*51\.750000 <double>\s*$/s,
    0,
    'output for 2.125.160.216 with lookup path'
);

_test_stderr(
    [ qw( --file this/path/better/not/exist.mmdb --ip 1.2.3.4 ) ],
    qr{Can't open this/path/better/not/exist.mmdb}s,
    2,
    'error for file that does not exist'
);

_test_stderr(
    ['--file', "$test_data_dir/GeoIP2-City-Test.mmdb", '--ip', 'not-an-ip-address' ],
    qr{Error from call to getaddrinfo for not-an-ip-address}s,
    3,
    'error for bad IP address'
);

_test_stderr(
    ['--file', "$test_data_dir/GeoIP2-City-Test.mmdb", '--ip', '10.2.3.4' ],
    qr{\QCould not find an entry for this IP address (10.2.3.4)}s,
    6,
    'error for bad PI address'
);

done_testing();

sub _test_stdout {
    my $args          = shift;
    my $expect_stdout = shift;
    my $expect_status = shift;
    my $desc          = shift;

    _test_both( $args, $expect_stdout, q{}, $expect_status, $desc );
}

sub _test_stderr {
    my $args          = shift;
    my $expect_stderr = shift;
    my $expect_status = shift;
    my $desc          = shift;

    _test_both( $args, undef, $expect_stderr, $expect_status, $desc );
}

sub _test_both {
    my $args          = shift;
    my $expect_stdout = shift;
    my $expect_stderr = shift;
    my $expect_status = shift;
    my $desc          = shift;

    my $stdout;
    my $stderr;
    run3(
        [ $mmdblookup, @{$args} ],
        \undef,
        \$stdout,
        \$stderr,
    );

    my $exit_status = $? >> 8;

    # We don't need to retest that the help output shows up for all errors
    if ( defined $expect_stdout ) {
        like(
            $stdout,
            $expect_stdout,
            "stdout for mmdblookup @{$args}"
        );
    }

    if ( ref $expect_stderr ) {
        like( $stderr, $expect_stderr, "stderr for mmdblookup @{$args}" );
    }
    else {
        is( $stderr, $expect_stderr, "stderr for mmdblookup @{$args}" );
    }

    is(
        $exit_status, $expect_status,
        "exit status was $expect_status for mmdblookup @{$args}"
    );
}
