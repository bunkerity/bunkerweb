#!/usr/bin/env perl

use strict;
use warnings;

use FindBin qw( $Bin );

_skip_tests_if_not_linux();
_skip_tests_if_required_modules_are_not_present();
_skip_tests_if_nm_is_not_present();
_test_libs_external_symbols();

done_testing();

sub _skip_tests_if_not_linux {
    return if $^O eq 'linux';

    print "1..0 # skip all tests skipped - this test requires Linux.\n";
    exit 0;
}

sub _skip_tests_if_required_modules_are_not_present {
    eval <<'EOF';
    use Test::More 0.88;
    use IPC::Run3 qw( run3 );
EOF

    if ($@) {
        print
            "1..0 # skip all tests skipped - these tests need the Test::More 0.88, IPC::Run3 modules:\n";
        print "$@";
        exit 0;
    }
}

sub _skip_tests_if_nm_is_not_present {
    run3(
        [ 'nm', '-V' ],
        \undef,
        \undef,
        \undef,
    );

    my $exit_status = $? >> 8;
    if ($exit_status) {
        print
            "1..0 # skipp all tests skipped - this test requires the command line utility `nm`.\n";
        exit 0;
    }
}

sub _test_libs_external_symbols {
    my @libs = _libs_to_test();

    if (@libs) {
        for my $lib (@libs) {
            _test_lib_external_symbols($lib);
        }
    }
    else {
        fail('No libs were found to test');
    }
}

sub _libs_to_test {
    my $lib_dir = "$Bin/../src/.libs";
    opendir my $dh, $lib_dir
        or die "Failed to open the lib dir at $lib_dir for reading: $!\n";
    my @libs = map { $lib_dir . q{/} . $_ }
        grep { $_ =~ m/\.so$/ } readdir $dh;
    closedir $dh;

    return @libs;
}

sub _test_lib_external_symbols {
    my $lib = shift;

    my $stdout;
    my $stderr;
    run3(
        [ 'nm', '-g', '--defined-only', $lib ],
        \undef,
        \$stdout,
        \$stderr,
    );

    my $exit_status = $? >> 8;
    ok( !$exit_status, 'nm returned a non-error status' )
        or diag($stderr);

    my @external_symbols = _extract_external_symbols($stdout);
    is_deeply(
        [ grep { $_ !~ m/^MMDB_/ } @external_symbols ],
        [],
        "$lib exports only MMDB_ symbols"
    );
}

sub _extract_external_symbols {
    my $nm_output = shift;

    my @lines = split /\r\n|\r|\n/, $nm_output;

    my @external_symbols;
    for my $line (@lines) {
        my @fields = split /\s+/, $line;
        die "Unexpected nm output for line $line\n"
            if @fields != 3;
        push @external_symbols, $fields[2];
    }

    return @external_symbols;
}
