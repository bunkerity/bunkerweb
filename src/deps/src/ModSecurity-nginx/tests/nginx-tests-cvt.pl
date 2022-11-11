#!/usr/bin/perl

#
# Script to adjust nginx tests to include ModSecurity directives.  It enables
# us to passively test nginx functionality with ModSecurity module enabled.
#

# sh command line variations:
#
# for i in *.t; do cp -n $i $i.orig; perl nginx-tests-cvt.pl < $i.orig > $i; done
# for i in *.t; do perl nginx-tests-cvt.pl < $i.orig > $i; done
# for i in *.t; do cp $i.orig $i; done

my $ignore = 0;
while (<STDIN>) {
	print $_;

	$ignore = 1	if (/^mail {/);					# skip mail_*.t mail blocks
	$ignore = 0	if (/^http {/);

	next		if ($ignore);

	if (/^ *server_name .*;$/) {

		next if (/^ *server_name *below;/);			# skip duplication on refresh.t
		next if (/^ *server_name *many4.example.com;/);		# skip duplication on http_server_name.t

		print "
        modsecurity on;
        modsecurity_rules '
        SecRuleEngine On
        SecDebugLogLevel 9
        SecRule ARGS \"\@streq whee\" \"id:10,phase:2\"
        SecRule ARGS \"\@streq whee\" \"id:11,phase:2\"
        ';
";

	}
}
