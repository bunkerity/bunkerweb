#!/usr/bin/env perl

use strict;
use warnings;
use autodie;
use utf8;

use Carp qw( croak );
use Cwd qw( abs_path );
use File::Basename qw( dirname );
use File::Slurp qw( read_file write_file );
use JSON::XS qw( decode_json );
use Math::Int128 qw( uint128 );
use MaxMind::DB::Writer::Serializer 0.100004;
use MaxMind::DB::Writer::Tree 0.100004;
use MaxMind::DB::Writer::Util qw( key_for_data );
use Net::Works::Network;
use Test::MaxMind::DB::Common::Util qw( standard_test_metadata );

my $Dir = dirname( abs_path($0) );

sub main {
    my @sizes = ( 24, 28, 32 );
    my @ipv4_range = ( '1.1.1.1', '1.1.1.32' );

    my @ipv4_subnets = Net::Works::Network->range_as_subnets(@ipv4_range);
    for my $record_size (@sizes) {
        write_test_db(
            $record_size,
            \@ipv4_subnets,
            { ip_version => 4 },
            'ipv4',
        );
    }

    write_broken_pointers_test_db(
        24,
        \@ipv4_subnets,
        { ip_version => 4 },
        'broken-pointers',
    );

    write_broken_search_tree_db(
        24,
        \@ipv4_subnets,
        { ip_version => 4 },
        'broken-search-tree',
    );

    my @ipv6_subnets = Net::Works::Network->range_as_subnets(
        '::1:ffff:ffff',
        '::2:0000:0059'
    );

    for my $record_size (@sizes) {
        write_test_db(
            $record_size,
            \@ipv6_subnets,
            { ip_version => 6 },
            'ipv6',
        );

        write_test_db(
            $record_size,
            [
                @ipv6_subnets,
                Net::Works::Network->range_as_subnets( @ipv4_range, 6 ),
            ],
            { ip_version => 6 },
            'mixed',
        );
    }

    write_decoder_test_db();
    write_deeply_nested_structures_db();

    write_geoip2_dbs();
    write_broken_geoip2_city_db();
    write_invalid_node_count();

    write_no_ipv4_tree_db();

    write_no_map_db( \@ipv4_subnets );

    write_test_serialization_data();

    write_db_with_metadata_pointers();
}

sub write_broken_pointers_test_db {
    no warnings 'redefine';

    my $orig_store_data = MaxMind::DB::Writer::Serializer->can('store_data');

    # This breaks the value of the record for the 1.1.1.32 network, causing it
    # to point outside the database.
    local *MaxMind::DB::Writer::Serializer::store_data = sub {
        my $data_pointer = shift->$orig_store_data(@_);
        my $value        = $_[1];
        if (   ref($value) eq 'HASH'
            && exists $value->{ip}
            && $value->{ip} eq '1.1.1.32' ) {

            $data_pointer += 100_000;
        }
        return $data_pointer;
    };

    # The next hack will poison the data section for the 1.1.16/28 subnet
    # value. It's value will be a pointer that resolves to an offset outside
    # the database.

    my $key_to_poison = key_for_data( { ip => '1.1.1.16' } );

    my $orig_position_for_data
        = MaxMind::DB::Writer::Serializer->can('_position_for_data');
    local *MaxMind::DB::Writer::Serializer::_position_for_data = sub {
        my $key = $_[1];

        if ( $key eq $key_to_poison ) {
            return 1_000_000;
        }
        else {
            return shift->$orig_position_for_data(@_);
        }
    };

    write_test_db(@_);

    return;
}

sub write_broken_search_tree_db {
    my $filename = ( write_test_db(@_) )[1];

    my $content = read_file( $filename, { binmode => ':raw' } );

    # This causes the right record of the first node to be 0, meaning it
    # points back to the top of the tree. This should never happen in a
    # database that follows the spec.
    substr( $content, 5, 1 ) = "\0";
    write_file( $filename, $content, { binmode => ':raw' } );

    return;
}

sub write_test_db {
    my $record_size     = shift;
    my $subnets         = shift;
    my $metadata        = shift;
    my $ip_version_name = shift;

    my $writer = MaxMind::DB::Writer::Tree->new(
        ip_version         => $subnets->[0]->version(),
        record_size        => $record_size,
        alias_ipv6_to_ipv4 => ( $subnets->[0]->version() == 6 ? 1 : 0 ),
        map_key_type_callback => sub { 'utf8_string' },
        standard_test_metadata(),
        %{$metadata},
    );

    for my $subnet ( @{$subnets} ) {
        $writer->insert_network(
            $subnet,
            { ip => $subnet->first()->as_string() }
        );
    }

    my $filename = sprintf(
        "$Dir/MaxMind-DB-test-%s-%i.mmdb",
        $ip_version_name,
        $record_size,
    );
    open my $fh, '>', $filename;

    $writer->write_tree($fh);

    close $fh;

    return ( $writer, $filename );
}

{
    # We will store this once for each subnet so we will also be testing
    # pointers, since the serializer will generate a pointer to this
    # structure.
    my %all_types = (
        utf8_string => 'unicode! ☯ - ♫',
        double      => 42.123456,
        bytes       => pack( 'N', 42 ),
        uint16      => 100,
        uint32      => 2**28,
        int32       => -1 * ( 2**28 ),
        uint64      => uint128(1) << 60,
        uint128     => uint128(1) << 120,
        array       => [ 1, 2, 3, ],
        map         => {
            mapX => {
                utf8_stringX => 'hello',
                arrayX       => [ 7, 8, 9 ],
            },
        },
        boolean => 1,
        float   => 1.1,
    );

    my %all_types_0 = (
        utf8_string => q{},
        double      => 0,
        bytes       => q{},
        uint16      => 0,
        uint32      => 0,
        int32       => 0,
        uint64      => uint128(0),
        uint128     => uint128(0),
        array       => [],
        map         => {},
        boolean     => 0,
        float       => 0,
    );

    sub write_decoder_test_db {
        my $writer = MaxMind::DB::Writer::Tree->new(
            ip_version    => 6,
            record_size   => 24,
            database_type => 'MaxMind DB Decoder Test',
            languages     => ['en'],
            description   => {
                en =>
                    'MaxMind DB Decoder Test database - contains every MaxMind DB data type',
            },
            alias_ipv6_to_ipv4       => 1,
            remove_reserved_networks => 0,
            map_key_type_callback    => sub {
                my $key = $_[0];
                $key =~ s/X$//;
                return $key eq 'array' ? [ 'array', 'uint32' ] : $key;
            },
        );

        my @subnets
            = map { Net::Works::Network->new_from_string( string => $_ ) }
            qw(
            ::1.1.1.0/120
            ::2.2.0.0/112
            ::3.0.0.0/104
            ::4.5.6.7/128
            abcd::/64
            1000::1234:0000/112
        );

        for my $subnet (@subnets) {
            $writer->insert_network(
                $subnet,
                \%all_types,
            );
        }

        $writer->insert_network(
            Net::Works::Network->new_from_string( string => '::0.0.0.0/128' ),
            \%all_types_0,
        );

        open my $fh, '>', "$Dir/MaxMind-DB-test-decoder.mmdb";
        $writer->write_tree($fh);
        close $fh;

        return;
    }
}

{
    my %nested = (
        map1 => {
            map2 => {
                array => [
                    {
                        map3 => { a => 1, b => 2, c => 3 },
                    },
                ],
            },
        },
    );

    sub write_deeply_nested_structures_db {
        my $writer = MaxMind::DB::Writer::Tree->new(
            ip_version    => 6,
            record_size   => 24,
            ip_version    => 6,
            database_type => 'MaxMind DB Nested Data Structures',
            languages     => ['en'],
            description   => {
                en =>
                    'MaxMind DB Nested Data Structures Test database - contains deeply nested map/array structures',
            },
            alias_ipv6_to_ipv4    => 1,
            map_key_type_callback => sub {
                my $key = shift;
                return
                      $key =~ /^map/ ? 'map'
                    : $key eq 'array' ? [ 'array', 'map' ]
                    :                   'uint32';
            }
        );

        my @subnets
            = map { Net::Works::Network->new_from_string( string => $_ ) }
            qw(
            ::1.1.1.0/120
            ::2.2.0.0/112
            ::3.0.0.0/104
            ::4.5.6.7/128
            abcd::/64
            1000::1234:0000/112
        );

        for my $subnet (@subnets) {
            $writer->insert_network(
                $subnet,
                \%nested,
            );
        }

        open my $fh, '>', "$Dir/MaxMind-DB-test-nested.mmdb";
        $writer->write_tree($fh);
        close $fh;

        return;
    }
}

sub write_geoip2_dbs {
    _write_geoip2_db( @{$_}, 'Test' )
        for (
        [ 'GeoIP2-Anonymous-IP',         1 ],
        [ 'GeoIP2-City',                 0 ],
        [ 'GeoIP2-Connection-Type',      0 ],
        [ 'GeoIP2-Country',              0 ],
        [ 'GeoIP2-DensityIncome',        0 ],
        [ 'GeoIP2-Domain',               0 ],
        [ 'GeoIP2-Enterprise',           0 ],
        [ 'GeoIP2-ISP',                  0 ],
        [ 'GeoIP2-Precision-Enterprise', 0 ],
        [ 'GeoLite2-ASN',                0 ],
        );
}

sub write_broken_geoip2_city_db {
    no warnings 'redefine';

    # This is how we _used_ to encode doubles. Storing them this way with the
    # current reader tools can lead to weird errors. This broken database is a
    # good way to test the robustness of reader code in the face of broken
    # databases.
    local *MaxMind::DB::Writer::Serializer::_encode_double = sub {
        my $self  = shift;
        my $value = shift;

        $self->_simple_encode( double => $value );
    };

    _write_geoip2_db( 'GeoIP2-City', 0, 'Test Broken Double Format' );
}

sub write_invalid_node_count {
    no warnings 'redefine';
    local *MaxMind::DB::Writer::Tree::node_count = sub { 100000 };

    _write_geoip2_db( 'GeoIP2-City', 0, 'Test Invalid Node Count' );
}

sub _universal_map_key_type_callback {
    my $map = {

        # languages
        de      => 'utf8_string',
        en      => 'utf8_string',
        es      => 'utf8_string',
        fr      => 'utf8_string',
        ja      => 'utf8_string',
        'pt-BR' => 'utf8_string',
        ru      => 'utf8_string',
        'zh-CN' => 'utf8_string',

        # production
        accuracy_radius                => 'uint16',
        autonomous_system_number       => 'uint32',
        autonomous_system_organization => 'utf8_string',
        average_income                 => 'uint32',
        city                           => 'map',
        code                           => 'utf8_string',
        confidence                     => 'uint16',
        connection_type                => 'utf8_string',
        continent                      => 'map',
        country                        => 'map',
        domain                         => 'utf8_string',
        geoname_id                     => 'uint32',
        is_anonymous                   => 'boolean',
        is_anonymous_proxy             => 'boolean',
        is_anonymous_vpn               => 'boolean',
        is_hosting_provider            => 'boolean',
        is_legitimate_proxy            => 'boolean',
        is_public_proxy                => 'boolean',
        is_satellite_provider          => 'boolean',
        is_tor_exit_node               => 'boolean',
        iso_code                       => 'utf8_string',
        isp                            => 'utf8_string',
        latitude                       => 'double',
        location                       => 'map',
        longitude                      => 'double',
        metro_code                     => 'uint16',
        names                          => 'map',
        organization                   => 'utf8_string',
        population_density             => 'uint32',
        postal                         => 'map',
        registered_country             => 'map',
        represented_country            => 'map',
        subdivisions                   => [ 'array', 'map' ],
        time_zone                      => 'utf8_string',
        traits                         => 'map',
        traits                         => 'map',
        type                           => 'utf8_string',
        user_type                      => 'utf8_string',

        # for testing only
        foo       => 'utf8_string',
        bar       => 'utf8_string',
        buzz      => 'utf8_string',
        our_value => 'utf8_string',
    };

    my $callback = sub {
        my $key = shift;

        return $map->{$key} || die <<"ERROR";
Unknown tree key '$key'.

The universal_map_key_type_callback doesn't know what type to use for the passed
key.  If you are adding a new key that will be used in a frozen tree / mmdb then
you should update the mapping in both our internal code and here.
ERROR
    };

    return $callback;
}

sub _write_geoip2_db {
    my $type                  = shift;
    my $populate_all_networks = shift;
    my $description           = shift;

    my $writer = MaxMind::DB::Writer::Tree->new(
        ip_version    => 6,
        record_size   => 28,
        ip_version    => 6,
        database_type => $type,
        languages     => [ 'en', $type eq 'GeoIP2-City' ? ('zh') : () ],
        description   => {
            en => ( $type =~ s/-/ /gr )
                . " $description Database (fake GeoIP2 data, for example purposes only)",
            $type eq 'GeoIP2-City' ? ( zh => '小型数据库' ) : (),
        },
        alias_ipv6_to_ipv4    => 1,
        map_key_type_callback => _universal_map_key_type_callback(),
    );

    _populate_all_networks($writer) if $populate_all_networks;

    my $nodes = decode_json(
        read_file(
            "$Dir/../source-data/$type-Test.json",
            binmode => ':raw'
        )
    );

    for my $node (@$nodes) {
        for my $network ( keys %$node ) {
            $writer->insert_network(
                Net::Works::Network->new_from_string( string => $network ),
                $node->{$network}
            );
        }
    }

    my $suffix = $description =~ s/ /-/gr;
    open my $output_fh, '>', "$Dir/$type-$suffix.mmdb";
    $writer->write_tree($output_fh);
    close $output_fh;

    return;
}

sub _populate_all_networks {
    my $writer = shift;

    my $max_uint128 = uint128(0) - 1;
    my @networks    = Net::Works::Network->range_as_subnets(
        Net::Works::Address->new_from_integer(
            integer => 0,
            version => 6,
        ),
        Net::Works::Address->new_from_integer(
            integer => $max_uint128,
            version => 6,
        ),
    );

    for my $network (@networks) {
        $writer->insert_network( $network => {} );
    }
}

sub write_no_ipv4_tree_db {
    my $subnets = shift;

    my $writer = MaxMind::DB::Writer::Tree->new(
        ip_version    => 6,
        record_size   => 24,
        ip_version    => 6,
        database_type => 'MaxMind DB No IPv4 Search Tree',
        languages     => ['en'],
        description   => {
            en => 'MaxMind DB No IPv4 Search Tree',
        },
        remove_reserved_networks => 0,
        root_data_type           => 'utf8_string',
        map_key_type_callback    => sub { {} },
    );

    my $subnet = Net::Works::Network->new_from_string( string => '::/64' );
    $writer->insert_network( $subnet, $subnet->as_string() );

    open my $output_fh, '>', "$Dir/MaxMind-DB-no-ipv4-search-tree.mmdb";
    $writer->write_tree($output_fh);
    close $output_fh;

    return;
}

# The point of this database is to provide something where we can test looking
# up a single value. In other words, each IP address points to a non-compound
# value, a string rather than a map or array.
sub write_no_map_db {
    my $subnets = shift;

    my $writer = MaxMind::DB::Writer::Tree->new(
        ip_version    => 4,
        record_size   => 24,
        database_type => 'MaxMind DB String Value Entries',
        languages     => ['en'],
        description   => {
            en =>
                'MaxMind DB String Value Entries (no maps or arrays as values)',
        },
        root_data_type        => 'utf8_string',
        map_key_type_callback => sub { {} },
    );

    for my $subnet ( @{$subnets} ) {
        $writer->insert_network( $subnet, $subnet->as_string() );
    }

    open my $output_fh, '>', "$Dir/MaxMind-DB-string-value-entries.mmdb";
    $writer->write_tree($output_fh);
    close $output_fh;

    return;
}

sub write_test_serialization_data {
    my $serializer = MaxMind::DB::Writer::Serializer->new(
        map_key_type_callback => sub { 'utf8_string' } );

    $serializer->store_data( map => { long_key  => 'long_value1' } );
    $serializer->store_data( map => { long_key  => 'long_value2' } );
    $serializer->store_data( map => { long_key2 => 'long_value1' } );
    $serializer->store_data( map => { long_key2 => 'long_value2' } );
    $serializer->store_data( map => { long_key  => 'long_value1' } );
    $serializer->store_data( map => { long_key2 => 'long_value2' } );

    open my $fh, '>', 'maps-with-pointers.raw';
    print {$fh} ${ $serializer->buffer() }
        or die "Cannot write to maps-with-pointers.raw: $!";
    close $fh;

    return;
}

sub write_db_with_metadata_pointers {
    my $repeated_string = 'Lots of pointers in metadata';
    my $writer          = MaxMind::DB::Writer::Tree->new(
        ip_version            => 6,
        record_size           => 24,
        map_key_type_callback => sub { 'utf8_string' },
        database_type         => $repeated_string,
        languages             => [ 'en', 'es', 'zh' ],
        description           => {
            en => $repeated_string,
            es => $repeated_string,
            zh => $repeated_string,
        },

    );

    _populate_all_networks($writer);

    open my $fh, '>', 'MaxMind-DB-test-metadata-pointers.mmdb';

    $writer->write_tree($fh);

    close $fh;
}

main();
