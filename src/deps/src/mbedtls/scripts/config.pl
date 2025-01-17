#!/usr/bin/env perl
# Backward compatibility redirection

## Copyright The Mbed TLS Contributors
## SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
##

my $py = $0;
$py =~ s/\.pl$/.py/ or die "Unable to determine the name of the Python script";
exec 'python3', $py, @ARGV;
print STDERR "$0: python3: $!. Trying python instead.\n";
exec 'python', $py, @ARGV;
print STDERR "$0: python: $!\n";
exit 127;
