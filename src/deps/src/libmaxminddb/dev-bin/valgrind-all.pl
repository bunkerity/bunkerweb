#!/usr/bin/env perl

# Note to run this you will probably want to build with ./configure
# --disable-shared. You don't want to valgrind the libtool script.
#
# Also make sure you compile the tests first (`make check').

use strict;
use warnings;

use File::Basename qw( basename );
use FindBin qw( $Bin );
use IPC::Run3;

my $top_dir = "$Bin/..";

my $output;

my @tests;
push @tests, glob "$top_dir/t/*_t";
push @tests, glob "$top_dir/t/*-t";

my @mmdblookup = (
    "$top_dir/bin/mmdblookup",
    '--file', "$top_dir/t/maxmind-db/test-data/MaxMind-DB-test-decoder.mmdb",
    '--ip',
);

# We want IPv4 and IPv6 addresses - one of each that exists in the db and one
# that doesn't
my @ips = ( '1.1.1.1', '10.0.0.0', 'abcd::', '0900::' );

my @cmds = (
    ( map { [ @mmdblookup, $_ ] } @ips ),
    ( map { [$_] } @tests ),
);

for my $cmd (@cmds) {
    my $output;
    run3(
        [ qw( valgrind -v --leak-check=full --show-leak-kinds=all -- ), @{$cmd} ],
        \undef,
        \$output,
        \$output,
    );

    $output =~ s/^(?!=).*\n//mg;

    my $marker = '-' x 60;
    print $marker, "\n", ( join q{ }, basename( shift @{$cmd} ), @{$cmd} ),
        "\n", $marker, "\n", $output,
        "\n\n";
}
