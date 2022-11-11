package TestDNS;

use strict;
use warnings;

use 5.010001;
use Test::Nginx::Socket::Lua -Base;
#use JSON::XS;

use constant {
    TYPE_A => 1,
    TYPE_SOA => 6,
    TYPE_TXT => 16,
    TYPE_CNAME => 5,
    TYPE_AAAA => 28,
    TYPE_SRV => 33,
    CLASS_INTERNET => 1,
};

sub encode_name ($);
sub encode_ipv4 ($);
sub encode_ipv6 ($);
sub encode_record ($);
sub gen_dns_reply ($$);

sub Test::Base::Filter::dns {
    my ($self, $code) = @_;

    my $args = $self->current_arguments;
    #warn "args: $args";
    if (defined $args && $args ne 'tcp' && $args ne 'udp') {
        die "Invalid argument to the \"dns\" filter: $args\n";
    }

    my $mode = $args // 'udp';

    my $block = $self->current_block;

    my $pointer_spec = $block->dns_pointers;
    my @pointers;
    if (defined $pointer_spec) {
        my @loops = split /\s*,\s*/, $pointer_spec;
        for my $loop (@loops) {
            my @nodes = split /\s*=>\s*/, $loop;
            my $prev;
            for my $n (@nodes) {
                if ($n !~ /^\d+$/ || $n == 0) {
                    die "bad name ID in the --- dns_pointers: $n\n";
                }

                if (!defined $prev) {
                    $prev = $n;
                    next;
                }

                $pointers[$prev] = $n;
            }
        }
    }

    my $input = eval $code;
    if ($@) {
        die "failed to evaluate code $code: $@\n";
    }

    if (!ref $input) {
        return $input;
    }

    if (ref $input eq 'ARRAY') {
        my @replies;
        for my $t (@$input) {
            push @replies, gen_dns_reply($t, $mode);
        }

        return \@replies;
    }

    if (ref $input eq 'HASH') {
        return gen_dns_reply($input, $mode);
    }

    return $input;
}

sub gen_dns_reply ($$) {
    my ($t, $mode) = @_;

    my @raw_names;
    push @raw_names, \($t->{qname});

    my $answers = $t->{answer} // [];
    if (!ref $answers) {
        $answers = [$answers];
    }

    my $authority_answers = $t->{authority} // [];
    if (!ref $authority_answers) {
        $authority_answers = [$authority_answers];
    }

    my $additional_answers = $t->{additional} // [];
    if (!ref $additional_answers) {
        $additional_answers = [$additional_answers];
    }

    for my $ans (@$answers) {
        push @raw_names, \($ans->{name});
        if (defined $ans->{cname}) {
            push @raw_names, \($ans->{cname});
        }
    }

    for my $nsans (@$authority_answers) {
        push @raw_names, \($nsans->{name});
        if (defined $nsans->{cname}) {
            push @raw_names, \($nsans->{cname});
        }
    }

    for my $arans (@$additional_answers) {
        push @raw_names, \($arans->{name});
        if (defined $arans->{cname}) {
            push @raw_names, \($arans->{cname});
        }
    }

    for my $rname (@raw_names) {
        $$rname = encode_name($$rname // "");
    }

    my $qname = $t->{qname};

    my $s = '';

    my $id = $t->{id} // 0;

    $s .= pack("n", $id);
    #warn "id: ", length($s), " ", encode_json([$s]);

    my $qr = $t->{qr} // 1;

    my $opcode = $t->{opcode} // 0;

    my $aa = $t->{aa} // 0;

    my $tc = $t->{tc} // 0;
    my $rd = $t->{rd} // 1;
    my $ra = $t->{ra} // 1;

    my $ad = $t->{ad} // 0;
    my $cd = $t->{cd} // 0;

    my $rcode = $t->{rcode} // 0;

    my $flags = ($qr << 15) + ($opcode << 11) + ($aa << 10) + ($tc << 9)
                + ($rd << 8) + ($ra << 7) + ($ad << 4) + ($cd << 5) + $rcode;

    #warn sprintf("flags: %b", $flags);

    $flags = pack("n", $flags);
    $s .= $flags;

    #warn "flags: ", length($flags), " ", encode_json([$flags]);

    my $qdcount = $t->{qdcount} // 1;
    my $ancount = $t->{ancount} // scalar @$answers;
    my $nscount = $t->{nscount} // scalar @$authority_answers;
    my $arcount = $t->{arcount} // scalar @$additional_answers;

    $s .= pack("nnnn", $qdcount, $ancount, $nscount, $arcount);

    #warn "qname: ", length($qname), " ", encode_json([$qname]);

    $s .= $qname;

    my $qs_type = $t->{qtype} // TYPE_A;
    my $qs_class = $t->{qclass} // CLASS_INTERNET;

    $s .= pack("nn", $qs_type, $qs_class);

    for my $ans (@$answers) {
        $s .= encode_record($ans);
    }

    for my $nsans (@$authority_answers) {
        $s .= encode_record($nsans);
    }

    for my $arans (@$additional_answers) {
        $s .= encode_record($arans);
    }

    if ($mode eq 'tcp') {
        return pack("n", length($s)) . $s;
    }

    return $s;
}

sub encode_ipv4 ($) {
    my $txt = shift;
    my @bytes = split /\./, $txt;
    return pack("CCCC", @bytes), 4;
}

sub encode_ipv6 ($) {
    my $txt = shift;
    my @groups = split /:/, $txt;
    my $nils = 0;
    my $nonnils = 0;
    for my $g (@groups) {
        if ($g eq '') {
            $nils++;
        } else {
            $nonnils++;
            $g = hex($g);
        }
    }

    my $total = $nils + $nonnils;
    if ($total > 8 ) {
        die "Invalid IPv6 address: too many groups: $total: $txt";
    }

    if ($nils) {
        my $found = 0;
        my @new_groups;
        for my $g (@groups) {
            if ($g eq '') {
                if ($found) {
                    next;
                }

                for (1 .. 8 - $nonnils) {
                    push @new_groups, 0;
                }

                $found = 1;

            } else {
                push @new_groups, $g;
            }
        }

        @groups = @new_groups;
    }

    if (@groups != 8) {
        die "Invalid IPv6 address: $txt: @groups\n";
    }

    #warn "IPv6 groups: @groups";

    return pack("nnnnnnnn", @groups), 16;
}

sub encode_name ($) {
    my $name = shift;
    $name =~ s/([^.]+)\.?/chr(length($1)) . $1/ge;
    $name .= "\0";
    return $name;
}

sub encode_record ($) {
    my $ans = shift;
    my $name = $ans->{name};
    my $type = $ans->{type};
    my $class = $ans->{class};
    my $ttl = $ans->{ttl};
    my $rdlength = $ans->{rdlength};
    my $rddata = $ans->{rddata};

    my $ipv4 = $ans->{ipv4};
    if (defined $ipv4) {
        my ($data, $len) = encode_ipv4($ipv4);
        $rddata //= $data;
        $rdlength //= $len;
        $type //= TYPE_A;
        $class //= CLASS_INTERNET;
    }

    my $ipv6 = $ans->{ipv6};
    if (defined $ipv6) {
        my ($data, $len) = encode_ipv6($ipv6);
        $rddata //= $data;
        $rdlength //= $len;
        $type //= TYPE_AAAA;
        $class //= CLASS_INTERNET;
    }

    my $cname = $ans->{cname};
    if (defined $cname) {
        $rddata //= $cname;
        $rdlength //= length $rddata;
        $type //= TYPE_CNAME;
        $class //= CLASS_INTERNET;
    }

    my $txt = $ans->{txt};
    if (defined $txt) {
        $rddata //= $txt;
        $rdlength //= length $rddata;
        $type //= TYPE_TXT;
        $class //= CLASS_INTERNET;
    }


    my $srv = $ans->{srv};
    if (defined $srv) {
        $rddata //= pack("nnn", $ans->{priority}, $ans->{weight}, $ans->{port}) . encode_name($srv);
        $rdlength //= length $rddata;
        $type //= TYPE_SRV;
        $class //= CLASS_INTERNET;
    }

    my $soa = $ans->{soa};
    if (defined $soa) {
        my $data = encode_name($soa) . encode_name($ans->{rname});
        $data .= pack("NNNNN", $ans->{serial}, $ans->{refresh}, $ans->{retry}, $ans->{expire}, $ans->{minimum});
        $rddata //= $data;
        $rdlength //= length $rddata;
        $type //= TYPE_SOA;
        $class //= CLASS_INTERNET;
    }

    $type //= 0;
    $class //= 0;
    $ttl //= 0;

    return $name . pack("nnNn", $type, $class, $ttl, $rdlength) . $rddata;
}

1
