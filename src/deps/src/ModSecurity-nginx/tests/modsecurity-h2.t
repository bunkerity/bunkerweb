#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity module (HTTP/2).

###############################################################################

use warnings;
use strict;

use Test::More;

BEGIN { use FindBin; chdir($FindBin::Bin); }

use lib 'lib';
use Test::Nginx;
use Test::Nginx::HTTP2;

###############################################################################

select STDERR; $| = 1;
select STDOUT; $| = 1;

my $t = Test::Nginx->new()->has(qw/http http_v2/);

$t->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    server {
        listen       127.0.0.1:8080 http2;
        server_name  localhost;

        location / {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecRule ARGS "@streq whee" "id:10,phase:2"
                SecRule ARGS "@streq whee" "id:11,phase:2"
            ';
        }
        location /phase1 {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:1,log,deny,status:403"
                SecRule ARGS "@streq redirect301" "id:1,phase:1,status:301,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq redirect302" "id:2,phase:1,status:302,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq block401" "id:3,phase:1,status:401,block"
                SecRule ARGS "@streq block403" "id:4,phase:1,status:403,block"
            ';
        }
        location /phase2 {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:2,log,deny,status:403"
                SecRule ARGS "@streq redirect301" "id:1,phase:2,status:301,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq redirect302" "id:2,phase:2,status:302,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq block401" "id:3,phase:2,status:401,block"
                SecRule ARGS "@streq block403" "id:4,phase:2,status:403,block"
            ';
        }
        location /phase3 {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecDefaultAction "phase:3,log,deny,status:403"
                SecRule ARGS "@streq redirect301" "id:1,phase:3,status:301,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq redirect302" "id:2,phase:3,status:302,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq block401" "id:3,phase:3,status:401,block"
                SecRule ARGS "@streq block403" "id:4,phase:3,status:403,block"
            ';
        }
        location /phase4 {
            modsecurity on;
            modsecurity_rules '
                SecRuleEngine On
                SecResponseBodyAccess On
                SecDefaultAction "phase:4,log,deny,status:403"
                SecRule ARGS "@streq redirect301" "id:1,phase:4,status:301,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq redirect302" "id:2,phase:4,status:302,redirect:http://www.modsecurity.org"
                SecRule ARGS "@streq block401" "id:3,phase:4,status:401,block"
                SecRule ARGS "@streq block403" "id:4,phase:4,status:403,block"
            ';
        }
    }
}
EOF

$t->write_file("/phase1", "should be moved/blocked before this.");
$t->write_file("/phase2", "should be moved/blocked before this.");
$t->write_file("/phase3", "should be moved/blocked before this.");
$t->write_file("/phase4", "should not be moved/blocked, headers delivered before phase 4.");
$t->run();
$t->plan(20);

###############################################################################

my ($phase, $s, $sid, $frames, $frame);

# Redirect (302)

for $phase (1 .. 3) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=redirect302" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
	is($frame->{headers}->{':status'}, 302, "redirect 302 - phase ${phase}");
}

SKIP: {
skip 'long test', 1 unless $ENV{TEST_NGINX_UNSAFE};

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/phase4?what=redirect302' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
is($frame, undef, 'redirect 302 - phase 4');
}

# Redirect (301)

for $phase (1 .. 3) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=redirect301" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
	is($frame->{headers}->{':status'}, 301, "redirect 301 - phase ${phase}");
}

SKIP: {
skip 'long test', 1 unless $ENV{TEST_NGINX_UNSAFE};

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/phase4?what=redirect301' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
is($frame, undef, 'redirect 301 - phase 4');
}

# Block (401)

for $phase (1 .. 3) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=block401" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
	is($frame->{headers}->{':status'}, 401, "block 401 - phase ${phase}");
}

SKIP: {
skip 'long test', 1 unless $ENV{TEST_NGINX_UNSAFE};

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/phase4?what=block401' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
is($frame, undef, 'block 401 - phase 4');
}

# Block (403)

for $phase (1 .. 3) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=block403" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "HEADERS" } @$frames;
	is($frame->{headers}->{':status'}, 403, "block 403 - phase ${phase}");
}

SKIP: {
skip 'long test', 1 unless $ENV{TEST_NGINX_UNSAFE};

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/phase4?what=block403' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
is($frame, undef, 'block 403 - phase 4');
}

# Nothing to detect

for $phase (1 .. 3) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=nothing" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "DATA" } @$frames;
	is($frame->{data}, "should be moved\/blocked before this.", "nothing phase ${phase}");
}

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => "/phase4?what=nothing" });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
is($frame->{data}, "should not be moved\/blocked, headers delivered before phase 4.", 'nothing phase 4');
