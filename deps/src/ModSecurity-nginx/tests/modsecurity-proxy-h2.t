#!/usr/bin/perl

# (C) Andrei Belov

# Tests for ModSecurity over the http proxy module (HTTP/2).

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

my $t = Test::Nginx->new()->has(qw/http http_v2 proxy/)->plan(23);

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
            proxy_pass http://127.0.0.1:8081;
            proxy_read_timeout 1s;
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
            proxy_pass http://127.0.0.1:8081;
            proxy_read_timeout 1s;
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
            proxy_pass http://127.0.0.1:8081;
            proxy_read_timeout 1s;
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
            proxy_pass http://127.0.0.1:8081;
            proxy_read_timeout 1s;
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
            proxy_pass http://127.0.0.1:8081;
            proxy_read_timeout 1s;
        }
    }
}

EOF

$t->run_daemon(\&http_daemon);
$t->run()->waitforsocket('127.0.0.1:' . port(8081));

###############################################################################

my ($phase, $s, $sid, $frames, $frame);

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/SEE-THIS/, "proxy request");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/multi' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
like($frame->{data}, qr/AND-THIS/, "proxy request with multiple packets");

$s = Test::Nginx::HTTP2->new();
$sid = $s->new_stream({ path => '/', method => 'HEAD' });
$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
($frame) = grep { $_->{type} eq "DATA" } @$frames;
unlike($frame->{data}, qr/SEE-THIS/, "proxy head request");

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
#like(http_get('/phase1?what=nothing'), qr/phase1\?what=nothing\' not found/, 'nothing phase 1');
#like(http_get('/phase2?what=nothing'), qr/phase2\?what=nothing\' not found/, 'nothing phase 2');
#like(http_get('/phase3?what=nothing'), qr/phase3\?what=nothing\' not found/, 'nothing phase 3');
#like(http_get('/phase4?what=nothing'), qr/phase4\?what=nothing\' not found/, 'nothing phase 4');

for $phase (1 .. 4) {
	$s = Test::Nginx::HTTP2->new();
	$sid = $s->new_stream({ path => "/phase${phase}?what=nothing" });
	$frames = $s->read(all => [{ sid => $sid, fin => 1 }]);
	($frame) = grep { $_->{type} eq "DATA" } @$frames;
	like($frame->{data}, qr/phase${phase}\?what=nothing\' not found/, "nothing phase ${phase}");
}

###############################################################################

sub http_daemon {
	my $server = IO::Socket::INET->new(
		Proto => 'tcp',
		LocalHost => '127.0.0.1:' . port(8081),
		Listen => 5,
		Reuse => 1
	)
		or die "Can't create listening socket: $!\n";

	local $SIG{PIPE} = 'IGNORE';

	while (my $client = $server->accept()) {
		$client->autoflush(1);

		my $headers = '';
		my $uri = '';

		while (<$client>) {
			$headers .= $_;
			last if (/^\x0d?\x0a?$/);
		}

		$uri = $1 if $headers =~ /^\S+\s+([^ ]+)\s+HTTP/i;

		if ($uri eq '/') {
			print $client <<'EOF';
HTTP/1.1 200 OK
Connection: close

EOF
			print $client "TEST-OK-IF-YOU-SEE-THIS"
				unless $headers =~ /^HEAD/i;

		} elsif ($uri eq '/multi') {

			print $client <<"EOF";
HTTP/1.1 200 OK
Connection: close

TEST-OK-IF-YOU-SEE-THIS
EOF

			select undef, undef, undef, 0.1;
			print $client 'AND-THIS';

		} else {

			print $client <<"EOF";
HTTP/1.1 404 Not Found
Connection: close

Oops, '$uri' not found
EOF
		}

		close $client;
	}
}

###############################################################################
