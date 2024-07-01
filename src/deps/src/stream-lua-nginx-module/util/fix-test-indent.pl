#!/usr/bin/env perl

use strict;
use warnings;

my ($entered, $indent, $delta);
while (<>) {
    if (/^(\s+)\w+_by_lua_block \{$/) {
        #die "HERE, enter";
        $entered = 1;
        $indent = $1;
        undef $delta;
        print;
        next;
    }

    if ($entered) {
        if (/^${indent}\}$/) {
            undef $entered;
            undef $indent;
            undef $delta;
            print;
            next;
        }

        if (/^${indent}(\s+)(.*)/) {
            my ($extra, $lua) = ($1, $2);
            if (!defined $delta) {
                $delta = length($extra);
                if ($delta > 4) {
                    $delta -= 4;
                } else {
                    $delta = 0;
                }
            }
            #warn "delta: $delta";
            if ($delta > 0) {
                $extra = " " x (length($extra) - $delta);
            }
            print "$indent$extra$lua\n";
            next;
        }

        if (/^\s*$/) {
            print;
            next;
        }

        undef $entered;
        undef $indent;
        undef $delta;
        print;
        next;
    }

    print;
    next;
}
