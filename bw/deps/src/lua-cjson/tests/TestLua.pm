package TestLua;

use Test::Base -Base;
use IPC::Run3;
use Cwd;

use Test::LongString;

our @EXPORT = qw( run_tests );

$ENV{LUA_CPATH} = "../?.so;;";
$ENV{LUA_PATH} = "../lua/?.lua;;";
#$ENV{LUA_PATH} = ($ENV{LUA_PATH} || "" ) . ';' . getcwd . "/runtime/?.lua" . ';;';

sub run_test ($) {
    my $block = shift;
    #print $json_xs->pretty->encode(\@new_rows);
    #my $res = #print $json_xs->pretty->encode($res);
    my $name = $block->name;

    my $lua = $block->lua or
        die "No --- lua specified for test $name\n";

    my $luafile = "test_case.lua";

    open my $fh, ">$luafile" or
        die "Cannot open $luafile for writing: $!\n";

    print $fh $lua;
    close $fh;

    my ($res, $err);

    my @cmd;

    if ($ENV{TEST_LUA_USE_VALGRIND}) {
        warn "$name\n";
        @cmd =  ('valgrind', '-q', '--leak-check=full', 'luajit', 'test_case.lua');
    } else {
        @cmd =  ('luajit', 'test_case.lua');
    }

    run3 \@cmd, undef, \$res, \$err;
    my $rc = $?;

    #warn "res:$res\nerr:$err\n";

    if (defined $block->err) {
        $err =~ /.*:.*:.*: (.*\s)?/;
        $err = $1;
        is $err, $block->err, "$name - err expected";

    } elsif ($rc) {
        die "Failed to execute --- lua for test $name: $err\n";

    } else {
        #is $res, $block->out, "$name - output ok";
        is $res, $block->out, "$name - output ok";
    }

    is $rc, ($block->exit || 0), "$name - exit code ok";
    #unlink 'test_case.lua' or warn "could not delete \'test_case.lua\':$!";
}

sub run_tests () {
    for my $block (blocks()) {
        run_test($block);
    }
}

1;
