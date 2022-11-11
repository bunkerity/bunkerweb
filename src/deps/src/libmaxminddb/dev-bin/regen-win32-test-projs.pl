#!/usr/bin/env perl

use strict;
use warnings;

use FindBin qw( $Bin );

use Data::UUID;
use File::Slurp qw( read_file write_file );
use Path::Iterator::Rule;

sub main {
    my $rule = Path::Iterator::Rule->new;
    $rule->file->name(qr/_t.c$/);

    my $ug = Data::UUID->new;

    my $template = read_file("$Bin/../projects/test.vcxproj.template");

    my @names;
    for my $file ( $rule->all("$Bin/../t/") ) {
        my ($name) = $file =~ /(\w*)_t.c$/;

        next unless $name;
        next if $name eq 'threads';

        push @names, $name;

        my $project = $template;

        $project =~ s/%TESTNAME%/$name/g;

        my $uuid = $ug->to_string( $ug->create );
        $project =~ s/%UUID%/$uuid/g;

        write_file( "$Bin/../projects/VS12-tests/$name.vcxproj", $project );
    }

    _modify_yml(@names);
}

sub _modify_yml {
    my @names = @_;

    my $exe_block = join "\n",
        map { "  - .\\projects\\VS12\\Debug\\test_${_}.exe" } @names;

    my $file   = "$Bin/../appveyor.yml";
    my $config = read_file($file);
    $config =~ s/(#EXES).*?(#ENDEXES)/$1\n$exe_block\n  $2/s;
    write_file( $file, $config );
}

main();
