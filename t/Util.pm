use strict;
package t::Util;

sub get_openresty_canon_version (@) {
    sprintf "%d.%03d%03d%03d", $_[0], $_[1], $_[2], $_[3];
}

sub get_openresty_version () {
    my $NginxBinary = $ENV{TEST_NGINX_BINARY} || 'nginx';
    my $out = `$NginxBinary -V 2>&1`;

    if (!defined $out || $? != 0) {
        bail_out("Failed to get the version of the OpenResty in PATH");
        die;
    }
    if ($out =~ m{openresty[^/]*/(\d+)\.(\d+)\.(\d+)\.(\d+)}s) {
        return get_openresty_canon_version($1, $2, $3, $4);
    }
    if ($out =~ m{nginx[^/]*/(\d+)\.(\d+)\.(\d+)}s) {
        return;
    }

    bail_out("Failed to parse the output of \"nginx -V\": $out\n");
    die;
}

sub skip_openresty {
    my ($op, $ver) = @_;
    my $OpenrestyVersion = get_openresty_version();

    if ($ver =~ m{(\d+)\.(\d+)\.(\d+)\.(\d+)}s) {
        $ver = get_openresty_canon_version($1, $2, $3, $4);
    } else {
        bail_out("Invalid skip_openresty() arg: $ver");
        die;
    }

    if (defined $OpenrestyVersion and eval "$OpenrestyVersion $op $ver") {
        return 1;
    }

    return;
}

our @EXPORT = qw(
    skip_openresty
);

1;

# vim: set ft=perl:
