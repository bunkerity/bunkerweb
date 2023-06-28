#!/usr/bin/perl -w
#
#

use strict;
use warnings;
use JSON;

my $dir = $ARGV[0];
my $out = $ARGV[1];

if (!($dir && $out))
{
    die "Use: ./mport-modsec-unit-tests.pl /path/to/modsec/tests /path/to/dest\n\n";
}


opendir(DIR, $dir) or die "Failed to open: \"$!\"";

while (my $file = readdir(DIR)) 
{
    my $orig_file = $file;
    $file = $dir . "/" . $file;
    next if not ($file =~ m/\.t$/);

    open(CFG, "<$file") || die "Failed to open \"$file\": $!";
    my @data = <CFG>;
    my @C;
    my $edata = q/@C = (/ . join("", @data) . q/)/;
    eval $edata;
    die "Failed to read test data \"$file\": $@" if ($@);
    unless (@C) {
        print "No tests defined for $file\n";
        next;
    }

    print "Loaded ".@C." tests from $file\n";
    my $json = to_json(\@C, {utf8 => 1, pretty => 1});
    my ($new_file) = $orig_file =~ m/(.*)\.t$/;
    $new_file = $out . "/" . $new_file . ".json";
    open (DFG, ">$new_file" ) || die "Failed to open: \"$file\": $!";

    print " Saving at: " . $new_file . "\n";
    print DFG $json;
    close(DFG);
    close(CFG);
}

closedir(DIR);
