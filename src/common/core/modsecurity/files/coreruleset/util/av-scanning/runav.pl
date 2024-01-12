#!/usr/bin/perl
#
# runav.pl
# Copyright (c) 2004-2011 Trustwave
#
# This script is an interface between ModSecurity and its
# ability to intercept files being uploaded through the
# web server, and ClamAV


$CLAMSCAN = "clamscan";

if ($#ARGV != 0) {
    print "Usage: modsec-clamscan.pl <filename>\n";
    exit;
}

my ($FILE) = shift @ARGV;

$cmd = "$CLAMSCAN --stdout --disable-summary $FILE";
$input = `$cmd`;
$input =~ m/^(.+)/;
$error_message = $1;

$output = "0 Unable to parse clamscan output [$1]";

if ($error_message =~ m/: Empty file\.?$/) {
    $output = "1 empty file";
}
elsif ($error_message =~ m/: (.+) ERROR$/) {
    $output = "0 clamscan: $1";
}
elsif ($error_message =~ m/: (.+) FOUND$/) {
    $output = "0 clamscan: $1";
}
elsif ($error_message =~ m/: OK$/) {
    $output = "1 clamscan: OK";
}

print "$output\n";
