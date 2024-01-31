package t::TestLJ;

use v5.10.1;
use Test::Base -Base;
use IPC::Run3;
use Cwd qw( cwd );
use Test::LongString;
use File::Temp qw( tempdir );

our @EXPORT = qw( run_tests );

$ENV{LUA_CPATH} = "../?.so;;";
$ENV{LUA_PATH} = "../lua/?.lua;;";
#$ENV{LUA_PATH} = ($ENV{LUA_PATH} || "" ) . ';' . getcwd . "/runtime/?.lua" . ';;';

my $cwd = cwd;

sub run_test ($) {
    my $block = shift;
    #print $json_xs->pretty->encode(\@new_rows);
    #my $res = #print $json_xs->pretty->encode($res);
    my $name = $block->name;

    my $lua = $block->lua or
        die "No --- lua specified for test $name\n";

    my $luafile = "test.lua";

    {
        my $dir = tempdir "testlj_XXXXXXX", CLEANUP => 1;
        chdir $dir or die "$name - Cannot chdir to $dir: $!";
        open my $fh, ">$luafile"
            or die "$name - Cannot open $luafile in $dir for writing: $!\n";
        print $fh $lua;
        close $fh;
    }

    my ($res, $err);

    my @cmd;

    if ($ENV{TEST_LJ_USE_VALGRIND}) {
        warn "$name\n";
        @cmd =  ('valgrind', '-q', '--leak-check=full', 'luajit',
                 defined($block->jv) ? '-jv' : (),
                 defined($block->jdump) ? '-jdump' : (),
                 $luafile);
    } else {
        @cmd =  ('luajit',
                 defined($block->jv) ? '-jv' : (),
                 defined($block->jdump) ? '-jdump' : (),
                 $luafile);
    }

    run3 \@cmd, undef, \$res, \$err;
    my $rc = $?;

    #warn "res:$res\nerr:$err\n";

    my $exp_rc = $block->exit // 0;

    is $exp_rc, $rc >> 8, "$name - exit code okay";

    my $exp_err = $block->err;
    if (defined $exp_err) {
        if ($err =~ /.*:.*:.*: (.*\s)?/) {
            $err = $1;
        }

	if (ref $exp_err) {
	  like $err, $exp_err, "$name - err like expected";

	} else {
	  is $err, $exp_err, "$name - err expected";
	}

    } elsif (defined $err && $err ne '') {
        warn "$name - STDERR:\n$err";
    }

    if (defined $block->out) {
        #is $res, $block->out, "$name - output ok";
        is $res, $block->out, "$name - output ok";

    } elsif (defined $res && $res ne '') {
        warn "$name - STDOUT:\n$res";
    }

    chdir $cwd or die $!;
}

sub run_tests () {
    for my $block (blocks()) {
        run_test($block);
    }
}

1;
