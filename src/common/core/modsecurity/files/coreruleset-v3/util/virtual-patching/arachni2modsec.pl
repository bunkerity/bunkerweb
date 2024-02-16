#!/opt/local/bin/perl -T

#############################################
# -=[ Virtual Patching Converter Script ]=- #
#       Converts arachni XML Output          #
#    https://github.com/Zapotek/arachni     #
#                                           #
#           arachni2modsec.pl               #
#             Version: 1.0                  #
#                                           #
#            Copyright 2011                 #
#   Trustwave's SpiderLabs Research Team    #
#           www.trustwave.com               #
#                                           #
#   Based On Code Originally Created by:    #
#            The Denim Group                #
#          www.denimgroup.com               #
#############################################

use XML::Smart;
use Switch;
use Data::Types qw(:all);
use Data::Validate::URI qw(is_uri);
use Getopt::Std;
use Acme::Comment type=>'C++', one_line=>1; #Block commenting, can be removed later

#############
# Variables #
#############

# [Configuration Vars]
my %param;
getopt("f",\%param);
$filename = $param{f};
my $all_vulnerabilities_filename = "$filename";

unless ($filename) {
    print "Flag:\n\n\t -f:\t path to arachni xml report file\nUsage:\n\n\t./arachni2modsec.pl -f ./arachni_report.xml\n\n";
    exit;
}


my $modsec_rules_file = "./modsecurity_crs_48_virtual_patches.conf";

# [End Config Vars]

my $VULN_CLASS_XSS = "Cross-Site Scripting (XSS)";
my $VULN_CLASS_SQLI = "SQL Injection";
my $VULN_CLASS_BLIND_SQLI = "Blind SQL Injection";
my $VULN_CLASS_LFI = "Path Traversal";
my $VULN_CLASS_RFI = "Remote file inclusion";
my $VULN_CLASS_HTTPRS = "Response splitting";

# Only the vulnerabilities in this array will have
# rules generated for them.
my @supported_vulns = ($VULN_CLASS_XSS, $VULN_CLASS_SQLI, $VULN_CLASS_BLIND_SQLI, $VULN_CLASS_LFI, $VULN_CLASS_RFI, $VULN_CLASS_HTTPRS);

my $num_rules_generated=0;
my $num_not_supported=0;
my $num_bad_urls=0;

my $wait_for_keypress=1;
my $request_failed=0;

my $all_vulns_xml;
my @type;
my @id;
my $vuln_count;

my $num_attacks_flag=0;
my $num_attacks_noflag=0;

# End Vars ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

#############
#   Main    #
#############

# Clean up env so perl doesn't complain
# when trying to run the restart snort
# script.
delete @ENV{qw(IFS CDPATH ENV BASH_ENV PATH)};

$all_vulns_xml = XML::Smart->new($all_vulnerabilities_filename);

@type = $all_vulns_xml->{arachni_report}{issues}{issue}('[@]','name');
@url = $all_vulns_xml->{arachni_report}{issues}{issue}('[@]','url');
@param = $all_vulns_xml->{arachni_report}{issues}{issue}('[@]','variable');

open(my $MODSEC_RULES, '>' , $modsec_rules_file) || die "Unable to open modsecurity rules file $modsec_rules_file";
$MODSEC_RULES->autoflush(1);

$vuln_count = 0;

foreach my $current_type (@type){
	print "==================================================================================================\n";
	print "Vulnerability[$vuln_count] -  Type: $current_type\n";

	if(exists {map { $_ => 1 } @supported_vulns}->{$current_type}){
		parseData(to_string($current_type));
	}else {
 		print "Vulnerability Type: $type is not supported in this version.\n";
		$num_not_supported++;
	}
	$vuln_count++;
}

close($MODSEC_RULES);

print "==================================================================================================\n";

print "\n\n************ END OF SCRIPT RESULTS *****************\n";
print "Number of Vulnerabilities Processed:	$vuln_count\n";
print "Number of ModSecurity rules generated:   $num_rules_generated\n";
print "Number of Unsupported vulns skipped:     $num_not_supported\n";
print "Number of bad URLs (rules not gen):      $num_bad_urls\n";
print "****************************************************\n\n";
print "----------------------------------------------------\n";
print "To activate the virtual patching file ($modsec_rules_file),\n";
print "copy it into the CRS \"base_rules\" directory and then create\n";
print "a symlink to it in the \"activated_rules\" directory.\n";
print "-----------------------------------------------------\n\n";


###############
# Subroutines #
###############
sub parseData
{
	my($vuln_str) = @_;
	my $vuln_detail_filename;
	my $current_vuln_xml;
	my $current_vuln_url;
	my $current_vuln_param;
	my $current_uricontent;
	my @current_params;
	my $id = $vuln_count;

	print "Found a $vuln_str vulnerability.\n";

	$current_vuln_xml = XML::Smart->new($all_vulnerabilities_filename);
	$current_vuln_url = $url[$vuln_count];

	print URL_LIST "$current_vuln_url\n";

	# Validate url (need separate sub?)
	print "Validating URL: $current_vuln_url\n";
	if(is_uri(to_string($current_vuln_url))){
		print "URL is well-formed\n";
		print "Continuing Rule Generation\n";
	} else {
		print "URL is NOT well-formed. Breaking Out of Rule Generation\n";
		$num_bad_urls++;

		# Waits for keypress in test mode so you can
		# see why the URL failed validation.
		if($test_mode){
			wait_for_keypress();
		}
		return;
	}

	$current_uricontent = get_uricontent($current_vuln_url);


	# Only need param if XSS attack,SQLINJ,XPATH
	# and maybe for HTTPRS, DT.
	# NOT for PRL and DI

	if(($vuln_str ne $VULN_CLASS_PRL) && ($vuln_str ne $VULN_CLASS_DI)){
		@current_params = $param[$vuln_count];

	}
	if(($vuln_str ne $VULN_CLASS_PRL) && ($vuln_str ne $VULN_CLASS_DI)){
			print "Current vulnerable Param(s): @current_params\n";
	}

	generate_patch($vuln_str,$current_uricontent,@current_params);


}


sub generate_patch
{
	my($type,$uricontent,@params,$current_vuln_xml) = @_;
	my $rule = "";
	$id = "1".$vuln_count;

	switch($type)
	{
		case ($VULN_CLASS_XSS)
		{
			if($uricontent ne "" && @params){
				foreach(@params){
					if($_ ne ""){
						# Check to see if each vulnerable parameter is valid
						# then generate a rule using both uricontent and the
						# parameter
						$rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/XSS',tag:'WASCTC/WASC-8',tag:'WASCTC/WASC-22',tag:'OWASP_TOP_10/A2',tag:'OWASP_AppSensor/IE1',tag:'PCI/6.5.1',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/XSS.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.xss_score=+%{tx.critical_anomaly_score},setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

							print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
							print "$VULN_CLASS_XSS (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
							$num_rules_generated++;
					}
				}
			}
		}

		case ($VULN_CLASS_SQLI)
		{

			if($uricontent ne "" && @params){
				foreach(@params){
					if($_ ne ""){
						$rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/SQL_INJECTION',tag:'WASCTC/WASC-19',tag:'OWASP_TOP_10/A1',tag:'OWASP_AppSensor/CIE1',tag:'PCI/6.5.2',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/SQL_INJECTION.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.sql_injection_score=+%{tx.critical_anomaly_score},setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

					print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
                                        print "$VULN_CLASS_SQLI (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
                                        $num_rules_generated++;


					}
				}
			}
		}

		case ($VULN_CLASS_BLIND_SQLI)
                {

                        if($uricontent ne "" && @params){
                                foreach(@params){
                                        if($_ ne ""){
                                                $rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/SQL_INJECTION',tag:'WASCTC/WASC-19',tag:'OWASP_TOP_10/A1',tag:'OWASP_AppSensor/CIE1',tag:'PCI/6.5.2',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/SQL_INJECTION.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.sql_injection_score=+%{tx.critical_anomaly_score},setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

                                        print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
                                        print "$VULN_CLASS_SQLI (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
                                        $num_rules_generated++;


                                        }
                                }
                        }
                }

		case ($VULN_CLASS_LFI)
		{
			if($uricontent ne "" && @params){
				foreach(@params){
					if($_ ne ""){
                                                $rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/LFI',tag:'WASCTC/WASC-33',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/LFI.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

                                        print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
                                        print "$VULN_CLASS_LFI (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
                                        $num_rules_generated++;


					}
				}
			}
		}

		case ($VULN_CLASS_RFI)
                {
                        if($uricontent ne "" && @params){
                                foreach(@params){
                                        if($_ ne ""){
                                                $rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/RFI',tag:'WASCTC/WASC-05',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/RFI.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

                                        print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
                                        print "$VULN_CLASS_LFI (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
                                        $num_rules_generated++;


                                        }
                                }
                        }
                }

		case ($VULN_CLASS_HTTPRS)
		{
                        if($uricontent ne "" && @params){
                                foreach(@params){
                                        if($_ ne ""){
                                                $rule = "SecRule REQUEST_FILENAME \"$uricontent\" \"chain,phase:2,t:none,block,msg:'Virtual Patch for $type',id:'$id',tag:'WEB_ATTACK/RESPONSE_SPLITTING',tag:'WASCTC/WASC-25',logdata:'%{MATCHED_VAR_NAME}',severity:'2'\"\n\tSecRule \&TX:\'\/RESPONSE_SPLITTING.*ARGS:$_\/\' \"\@gt 0\" \"setvar:tx.anomaly_score=+%{tx.critical_anomaly_score}\"";

                                        print $MODSEC_RULES "#\n# Arachni Virtual Patch Details:\n# ID: $id\n# Type: $type\n# Vulnerable URL: $uricontent\n# Vulnerable Parameter: $_\n#\n".$rule."\n\n";
                                        print "$VULN_CLASS_RFI (uricontent and param) rule successfully generated and saved in $modsec_rules_file.\n";
                                        $num_rules_generated++;


                                        }
                                }
                        }
                }

	}
}

sub get_uricontent
{
	my($url) = @_;
	my $regex = "http:\/\/+[a-zA-Z0-9.:-]*\/";

	# First, trim the first part out of the URL:
	# http://.../
	$url =~ /$regex/;
	substr($url,index($url,$&),length($&)) = "";

	# If the URL contains a php or cgi query with
	# one or more params and values, trim those out.
	# Trim from the question mark to the end.
	if($url =~ /\?/){
		substr($url,index($url,"?")) = "";
	}
	return $url;

}
