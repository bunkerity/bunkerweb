package t::TestMLCache;

use strict;
use Test::Nginx::Socket::Lua -Base;
use Cwd qw(cwd);

our $pwd = cwd();

our @EXPORT = qw(
    $pwd
    skip_openresty
);

my $PackagePath = qq{lua_package_path "$pwd/lib/?.lua;;";};

my $HttpConfig = qq{
    lua_shared_dict  cache_shm      1m;
    lua_shared_dict  cache_shm_miss 1m;
    lua_shared_dict  locks_shm      1m;
    lua_shared_dict  ipc_shm        1m;

    init_by_lua_block {
        -- local verbose = true
        local verbose = false
        local outfile = "$Test::Nginx::Util::ErrLogFile"
        -- local outfile = "/tmp/v.log"
        if verbose then
            local dump = require "jit.dump"
            dump.on(nil, outfile)
        else
            local v = require "jit.v"
            v.on(outfile)
        end

        require "resty.core"
        -- jit.opt.start("hotloop=1")
        -- jit.opt.start("loopunroll=1000000")
        -- jit.off()
    }
};

add_block_preprocessor(sub {
    my $block = shift;

    if (!defined $block->request) {
        $block->set_value("request", "GET /t");
    }

    my $http_config = $block->http_config || '';
    $http_config .= $PackagePath;

    if ($http_config !~ m/init_by_lua_block/) {
        $http_config .= $HttpConfig;
    }

    $block->set_value("http_config", $http_config);
});

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

sub skip_openresty ($$) {
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
}

no_long_string();

1;
