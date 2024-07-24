#!/usr/bin/env perl
#
# Create one regexp from a set of regexps.
# Regexps can be submitted via standard input, one per line.
#
# Requires Regexp::Assemble Perl module.
# To install: cpan install Regexp::Assemble
#
# See: https://coreruleset.org/20190826/optimizing-regular-expressions/
#

use strict;
use Regexp::Assemble;

my $ra = Regexp::Assemble->new;
while (<>)
{
  $ra->add($_);
}
print $ra->as_string() . "\n";
