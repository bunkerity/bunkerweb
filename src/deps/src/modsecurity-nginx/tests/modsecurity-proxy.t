#!/usr/bin/perl


# Tests for ModSecurity over the http proxy module.

###############################################################################

use warnings;
use strict;

use Test::More;

BEGIN { use FindBin; chdir($FindBin::Bin); }

use lib 'lib';
use Test::Nginx;

###############################################################################

select STDERR; $| = 1;
select STDOUT; $| = 1;

my $t = Test::Nginx->new()->has(qw/http proxy/)->plan(23);

$t->write_file_expand('nginx.conf', <<'EOF');

%%TEST_GLOBALS%%

daemon off;

events {
}

http {
    %%TEST_GLOBALS_HTTP%%

    server {
        listen       127.0.0.1:8080;
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

$t->todo_alerts();
$t->run_daemon(\&http_daemon);
$t->run()->waitforsocket('127.0.0.1:' . port(8081));

###############################################################################

like(http_get('/'), qr/SEE-THIS/, 'proxy request');
like(http_get('/multi'), qr/AND-THIS/, 'proxy request with multiple packets');

unlike(http_head('/'), qr/SEE-THIS/, 'proxy head request');


# Redirect (302)
like(http_get('/phase1?what=redirect302'), qr/^HTTP.*302/, 'redirect 302 - phase 1');
like(http_get('/phase2?what=redirect302'), qr/^HTTP.*302/, 'redirect 302 - phase 2');
like(http_get('/phase3?what=redirect302'), qr/^HTTP.*302/, 'redirect 302 - phase 3');
is(http_get('/phase4?what=redirect302'), '', 'redirect 302 - phase 4');

# Redirect (301)
like(http_get('/phase1?what=redirect301'), qr/^HTTP.*301/, 'redirect 301 - phase 1');
like(http_get('/phase2?what=redirect301'), qr/^HTTP.*301/, 'redirect 301 - phase 2');
like(http_get('/phase3?what=redirect301'), qr/^HTTP.*301/, 'redirect 301 - phase 3');
is(http_get('/phase4?what=redirect301'), '', 'redirect 301 - phase 4');

# Block (401)
like(http_get('/phase1?what=block401'), qr/^HTTP.*401/, 'block 401 - phase 1');
like(http_get('/phase2?what=block401'), qr/^HTTP.*401/, 'block 401 - phase 2');
like(http_get('/phase3?what=block401'), qr/^HTTP.*401/, 'block 401 - phase 3');
is(http_get('/phase4?what=block401'), '', 'block 401 - phase 4');

# Block (403)
like(http_get('/phase1?what=block403'), qr/^HTTP.*403/, 'block 403 - phase 1');
like(http_get('/phase2?what=block403'), qr/^HTTP.*403/, 'block 403 - phase 2');
like(http_get('/phase3?what=block403'), qr/^HTTP.*403/, 'block 403 - phase 3');
is(http_get('/phase4?what=block403'), '', 'block 403 - phase 4');

# Nothing to detect
like(http_get('/phase1?what=nothing'), qr/phase1\?what=nothing\' not found/, 'nothing phase 1');
like(http_get('/phase2?what=nothing'), qr/phase2\?what=nothing\' not found/, 'nothing phase 2');
like(http_get('/phase3?what=nothing'), qr/phase3\?what=nothing\' not found/, 'nothing phase 3');
like(http_get('/phase4?what=nothing'), qr/phase4\?what=nothing\' not found/, 'nothing phase 4');


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
