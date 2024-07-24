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
  # Handle possessive qualifiers
  # https://rt.cpan.org/Public/Bug/Display.html?id=50228#txn-672717
  my $arr = $ra->lexstr($_);
  for (my $n = 0; $n < $#$arr - 1; ++$n)
  {
    if ($arr->[$n] =~ /\+$/ and $arr->[$n + 1] eq '+') {
      $arr->[$n] .= splice(@$arr, $n + 1, 1);
    }
  }
  $ra->insert(@$arr);
}
print $ra->as_string() . "\n";
