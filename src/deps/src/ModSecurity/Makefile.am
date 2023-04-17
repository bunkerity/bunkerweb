
if TEST_UTILITIES
export MAYBE_TEST = test
endif

if EXAMPLES
export MAYBE_EXAMPLES = examples
endif


SUBDIRS = \
	others \
	src \
	doc \
	tools \
	$(MAYBE_EXAMPLES) \
	$(MAYBE_TEST)



# make clean
CLEANFILES = 

ACLOCAL_AMFLAGS = -I build

# make maintainer-clean
MAINTAINERCLEANFILES = \
	aclocal.m4 \
	ar-lib \
	build/libtool.m4 \
	build/lt~obsolete.m4 \
	build/ltoptions.m4 \
	build/ltsugar.m4 \
	build/ltversion.m4 \
	coding-style.txt \
	compile \
	config.guess \
	config.sub \
	configure \
	cppcheck.txt \
	depcomp \
	install-sh \
	ltmain.sh \
	Makefile.in \
	missing \
	test/modsec-shared-collections \
	test/modsec-shared-collections-lock \
	test-suite-drd.log \
	test-suite-helgrind.log \
	test-suite-memcheck.log \
	ylwrap

parser:
	cat src/parser/seclang-parser.hh | sed "s/return \*new (yyas_<T> ()) T (t)/return *new (yyas_<T> ()) T (std::move((T\&)t))/g"  > src/parser/seclang-parser.hh.fix && mv src/parser/seclang-parser.hh.fix src/parser/seclang-parser.hh



cppcheck:
	@cppcheck -U YYSTYPE -U MBEDTLS_MD5_ALT -U MBEDTLS_SHA1_ALT \
		-D MS_CPPCHECK_DISABLED_FOR_PARSER -U YY_USER_INIT \
		--suppressions-list=./test/cppcheck_suppressions.txt \
		--enable=warning,style,performance,portability,unusedFunction,missingInclude \
		--inconclusive \
		--template="warning: {file},{line},{severity},{id},{message}" \
		-I headers -I . -I others -I src -I others/mbedtls -I src/parser \
		--error-exitcode=1 \
		-i "src/parser/seclang-parser.cc" -i "src/parser/seclang-scanner.cc" \
		--force --verbose .


check-static: cppcheck

check-style: check-coding-style

check-coding-style:
	@cpplint.py \
		$$(find . -name "*.h" -o -name "*.cc" | xargs) 2>&1 \
 		| egrep -v $$(echo -n "catchall" ; \
	  		for i in $$(cat test/coding_style_suppressions.txt); do echo -n "|"$$i; done) \
		| sed 's/^\./warning: ./g' > coding-style.txt
	-cat coding-style.txt


@VALGRIND_CHECK_RULES@
VALGRIND_SUPPRESSIONS_FILES = valgrind_suppressions.txt

LOG_DRIVER = env $(SHELL) $(top_srcdir)/test/custom-test-driver
AM_TESTS_ENVIRONMENT=AUTOMAKE_TESTS=true; export AUTOMAKE_TESTS;
LOG_COMPILER=test/test-suite.sh

# for i in `find test/test-cases -iname *.json`; do echo TESTS+=$i; done
TESTS=
TESTS+=test/test-cases/regression/action-allow.json
TESTS+=test/test-cases/regression/action-block.json
TESTS+=test/test-cases/regression/action-ctl_request_body_access.json
TESTS+=test/test-cases/regression/action-ctl_request_body_processor.json
TESTS+=test/test-cases/regression/action-ctl_request_body_processor_urlencoded.json
TESTS+=test/test-cases/regression/action-ctl_rule_engine.json
TESTS+=test/test-cases/regression/action-ctl_audit_engine.json
TESTS+=test/test-cases/regression/action-ctl_rule_remove_by_id.json
TESTS+=test/test-cases/regression/action-ctl_rule_remove_by_tag.json
TESTS+=test/test-cases/regression/action-ctl_rule_remove_target_by_id.json
TESTS+=test/test-cases/regression/action-ctl_rule_remove_target_by_tag.json
TESTS+=test/test-cases/regression/action-disruptive.json
TESTS+=test/test-cases/regression/action-exec.json
TESTS+=test/test-cases/regression/action-id.json
TESTS+=test/test-cases/regression/action-initcol.json
TESTS+=test/test-cases/regression/action-msg.json
TESTS+=test/test-cases/regression/action-setenv.json
TESTS+=test/test-cases/regression/action-setrsc.json
TESTS+=test/test-cases/regression/action-setsid.json
TESTS+=test/test-cases/regression/action-setuid.json
TESTS+=test/test-cases/regression/actions.json
TESTS+=test/test-cases/regression/action-skip.json
TESTS+=test/test-cases/regression/action-tag.json
TESTS+=test/test-cases/regression/action-tnf-base64.json
TESTS+=test/test-cases/regression/action-xmlns.json
TESTS+=test/test-cases/regression/auditlog.json
TESTS+=test/test-cases/regression/collection-case-insensitive.json
TESTS+=test/test-cases/regression/collection-lua.json
TESTS+=test/test-cases/regression/collection-regular_expression_selection.json
TESTS+=test/test-cases/regression/collection-resource.json
TESTS+=test/test-cases/regression/collection-tx.json
TESTS+=test/test-cases/regression/collection-tx-with-macro.json
TESTS+=test/test-cases/regression/config-body_limits.json
TESTS+=test/test-cases/regression/config-calling_phases_by_name.json
TESTS+=test/test-cases/regression/config-include-bad.json
TESTS+=test/test-cases/regression/config-include.json
TESTS+=test/test-cases/regression/config-remove_by_id.json
TESTS+=test/test-cases/regression/config-remove_by_msg.json
TESTS+=test/test-cases/regression/config-remove_by_tag.json
TESTS+=test/test-cases/regression/config-response_type.json
TESTS+=test/test-cases/regression/config-secdefaultaction.json
TESTS+=test/test-cases/regression/config-secremoterules.json
TESTS+=test/test-cases/regression/config-update-action-by-id.json
TESTS+=test/test-cases/regression/config-update-target-by-id.json
TESTS+=test/test-cases/regression/config-update-target-by-msg.json
TESTS+=test/test-cases/regression/config-update-target-by-tag.json
TESTS+=test/test-cases/regression/config-xml_external_entity.json
TESTS+=test/test-cases/regression/debug_log.json
TESTS+=test/test-cases/regression/directive-sec_rule_script.json
TESTS+=test/test-cases/regression/issue-1152.json
TESTS+=test/test-cases/regression/issue-1528.json
TESTS+=test/test-cases/regression/issue-1565.json
TESTS+=test/test-cases/regression/issue-1576.json
TESTS+=test/test-cases/regression/issue-1591.json
TESTS+=test/test-cases/regression/issue-1725.json
TESTS+=test/test-cases/regression/issue-1743.json
TESTS+=test/test-cases/regression/issue-1785.json
TESTS+=test/test-cases/regression/issue-1812.json
TESTS+=test/test-cases/regression/issue-1831.json
TESTS+=test/test-cases/regression/issue-1844.json
TESTS+=test/test-cases/regression/issue-1850.json
TESTS+=test/test-cases/regression/issue-1941.json
TESTS+=test/test-cases/regression/issue-1943.json
TESTS+=test/test-cases/regression/issue-1956.json
TESTS+=test/test-cases/regression/issue-1960.json
TESTS+=test/test-cases/regression/issue-2099.json
TESTS+=test/test-cases/regression/issue-2000.json
TESTS+=test/test-cases/regression/issue-2111.json
TESTS+=test/test-cases/regression/issue-2196.json
TESTS+=test/test-cases/regression/issue-2423-msg-in-chain.json
TESTS+=test/test-cases/regression/issue-2427.json
TESTS+=test/test-cases/regression/issue-2296.json
TESTS+=test/test-cases/regression/issue-394.json
TESTS+=test/test-cases/regression/issue-849.json
TESTS+=test/test-cases/regression/issue-960.json
TESTS+=test/test-cases/regression/misc.json
TESTS+=test/test-cases/regression/misc-variable-under-quotes.json
TESTS+=test/test-cases/regression/offset-variable.json
TESTS+=test/test-cases/regression/operator-detectsqli.json
TESTS+=test/test-cases/regression/operator-detectxss.json
TESTS+=test/test-cases/regression/operator-fuzzyhash.json
TESTS+=test/test-cases/regression/operator-inpectFile.json
TESTS+=test/test-cases/regression/operator-ipMatchFromFile.json
TESTS+=test/test-cases/regression/operator-pm.json
TESTS+=test/test-cases/regression/operator-rx.json
TESTS+=test/test-cases/regression/operator-rxGlobal.json
TESTS+=test/test-cases/regression/operator-UnconditionalMatch.json
TESTS+=test/test-cases/regression/operator-validate-byte-range.json
TESTS+=test/test-cases/regression/operator-verifycc.json
TESTS+=test/test-cases/regression/operator-verifycpf.json
TESTS+=test/test-cases/regression/operator-verifyssn.json
TESTS+=test/test-cases/regression/operator-verifysvnr.json
TESTS+=test/test-cases/regression/request-body-parser-json.json
TESTS+=test/test-cases/regression/request-body-parser-multipart-crlf.json
TESTS+=test/test-cases/regression/request-body-parser-multipart.json
TESTS+=test/test-cases/regression/request-body-parser-xml.json
TESTS+=test/test-cases/regression/request-body-parser-xml-validade-dtd.json
TESTS+=test/test-cases/regression/rule-920120.json
TESTS+=test/test-cases/regression/rule-920200.json
TESTS+=test/test-cases/regression/rule-920274.json
TESTS+=test/test-cases/regression/secaction.json
TESTS+=test/test-cases/regression/secargumentslimit.json
TESTS+=test/test-cases/regression/sec_component_signature.json
TESTS+=test/test-cases/regression/secmarker.json
TESTS+=test/test-cases/regression/secruleengine.json
TESTS+=test/test-cases/regression/transformation-none.json
TESTS+=test/test-cases/regression/transformations.json
TESTS+=test/test-cases/regression/variable-ARGS_COMBINED_SIZE.json
TESTS+=test/test-cases/regression/variable-ARGS_GET.json
TESTS+=test/test-cases/regression/variable-ARGS_GET_NAMES.json
TESTS+=test/test-cases/regression/variable-ARGS.json
TESTS+=test/test-cases/regression/variable-ARGS_NAMES.json
TESTS+=test/test-cases/regression/variable-ARGS_POST.json
TESTS+=test/test-cases/regression/variable-ARGS_POST_NAMES.json
TESTS+=test/test-cases/regression/variable-AUTH_TYPE.json
TESTS+=test/test-cases/regression/variable-DURATION.json
TESTS+=test/test-cases/regression/variable-ENV.json
TESTS+=test/test-cases/regression/variable-FILES_COMBINED_SIZE.json
TESTS+=test/test-cases/regression/variable-FILES.json
TESTS+=test/test-cases/regression/variable-FILES_NAMES.json
TESTS+=test/test-cases/regression/variable-FILES_SIZES.json
TESTS+=test/test-cases/regression/variable-FULL_REQUEST.json
TESTS+=test/test-cases/regression/variable-FULL_REQUEST_LENGTH.json
TESTS+=test/test-cases/regression/variable-GEO.json
TESTS+=test/test-cases/regression/variable-HIGHEST_SEVERITY.json
TESTS+=test/test-cases/regression/variable-INBOUND_DATA_ERROR.json
TESTS+=test/test-cases/regression/variable-MATCHED_VAR.json
TESTS+=test/test-cases/regression/variable-MATCHED_VAR_NAME.json
TESTS+=test/test-cases/regression/variable-MATCHED_VARS.json
TESTS+=test/test-cases/regression/variable-MATCHED_VARS_NAMES.json
TESTS+=test/test-cases/regression/variable-MODSEC_BUILD.json
TESTS+=test/test-cases/regression/variable-MULTIPART_CRLF_LF_LINES.json
TESTS+=test/test-cases/regression/variable-MULTIPART_FILENAME.json
TESTS+=test/test-cases/regression/variable-MULTIPART_INVALID_HEADER_FOLDING.json
TESTS+=test/test-cases/regression/variable-MULTIPART_NAME.json
TESTS+=test/test-cases/regression/variable-MULTIPART_PART_HEADERS.json
TESTS+=test/test-cases/regression/variable-MULTIPART_STRICT_ERROR.json
TESTS+=test/test-cases/regression/variable-MULTIPART_UNMATCHED_BOUNDARY.json
TESTS+=test/test-cases/regression/variable-OUTBOUND_DATA_ERROR.json
TESTS+=test/test-cases/regression/variable-PATH_INFO.json
TESTS+=test/test-cases/regression/variable-QUERY_STRING.json
TESTS+=test/test-cases/regression/variable-REMOTE_ADDR.json
TESTS+=test/test-cases/regression/variable-REMOTE_HOST.json
TESTS+=test/test-cases/regression/variable-REMOTE_PORT.json
TESTS+=test/test-cases/regression/variable-REMOTE_USER.json
TESTS+=test/test-cases/regression/variable-REQBODY_PROCESSOR_ERROR.json
TESTS+=test/test-cases/regression/variable-REQBODY_PROCESSOR.json
TESTS+=test/test-cases/regression/variable-REQUEST_BASENAME.json
TESTS+=test/test-cases/regression/variable-REQUEST_BODY.json
TESTS+=test/test-cases/regression/variable-REQUEST_BODY_LENGTH.json
TESTS+=test/test-cases/regression/variable-REQUEST_COOKIES.json
TESTS+=test/test-cases/regression/variable-REQUEST_COOKIES_NAMES.json
TESTS+=test/test-cases/regression/variable-REQUEST_FILENAME.json
TESTS+=test/test-cases/regression/variable-REQUEST_HEADERS.json
TESTS+=test/test-cases/regression/variable-REQUEST_HEADERS_NAMES.json
TESTS+=test/test-cases/regression/variable-REQUEST_LINE.json
TESTS+=test/test-cases/regression/variable-REQUEST_METHOD.json
TESTS+=test/test-cases/regression/variable-REQUEST_PROTOCOL.json
TESTS+=test/test-cases/regression/variable-REQUEST_URI.json
TESTS+=test/test-cases/regression/variable-REQUEST_URI_RAW.json
TESTS+=test/test-cases/regression/variable-RESPONSE_BODY.json
TESTS+=test/test-cases/regression/variable-RESPONSE_CONTENT_LENGTH.json
TESTS+=test/test-cases/regression/variable-RESPONSE_CONTENT_TYPE.json
TESTS+=test/test-cases/regression/variable-RESPONSE_HEADERS.json
TESTS+=test/test-cases/regression/variable-RESPONSE_HEADERS_NAMES.json
TESTS+=test/test-cases/regression/variable-RESPONSE_PROTOCOL.json
TESTS+=test/test-cases/regression/variable-RULE.json
TESTS+=test/test-cases/regression/variable-SERVER_ADDR.json
TESTS+=test/test-cases/regression/variable-SERVER_NAME.json
TESTS+=test/test-cases/regression/variable-SERVER_PORT.json
TESTS+=test/test-cases/regression/variable-SESSIONID.json
TESTS+=test/test-cases/regression/variable-STATUS.json
TESTS+=test/test-cases/regression/variable-TIME_DAY.json
TESTS+=test/test-cases/regression/variable-TIME_EPOCH.json
TESTS+=test/test-cases/regression/variable-TIME_HOUR.json
TESTS+=test/test-cases/regression/variable-TIME.json
TESTS+=test/test-cases/regression/variable-TIME_MIN.json
TESTS+=test/test-cases/regression/variable-TIME_MON.json
TESTS+=test/test-cases/regression/variable-TIME_SEC.json
TESTS+=test/test-cases/regression/variable-TIME_WDAY.json
TESTS+=test/test-cases/regression/variable-TIME_YEAR.json
TESTS+=test/test-cases/regression/variable-TX.json
TESTS+=test/test-cases/regression/variable-UNIQUE_ID.json
TESTS+=test/test-cases/regression/variable-URLENCODED_ERROR.json
TESTS+=test/test-cases/regression/variable-USERID.json
TESTS+=test/test-cases/regression/variable-variation-count.json
TESTS+=test/test-cases/regression/variable-variation-exclusion.json
TESTS+=test/test-cases/regression/variable-WEBAPPID.json
TESTS+=test/test-cases/regression/variable-WEBSERVER_ERROR_LOG.json
TESTS+=test/test-cases/regression/variable-XML.json
TESTS+=test/test-cases/secrules-language-tests/operators/beginsWith.json
TESTS+=test/test-cases/secrules-language-tests/operators/contains.json
TESTS+=test/test-cases/secrules-language-tests/operators/containsWord.json
TESTS+=test/test-cases/secrules-language-tests/operators/detectSQLi.json
TESTS+=test/test-cases/secrules-language-tests/operators/detectXSS.json
TESTS+=test/test-cases/secrules-language-tests/operators/endsWith.json
TESTS+=test/test-cases/secrules-language-tests/operators/eq.json
TESTS+=test/test-cases/secrules-language-tests/operators/ge.json
TESTS+=test/test-cases/secrules-language-tests/operators/geoLookup.json
TESTS+=test/test-cases/secrules-language-tests/operators/gt.json
TESTS+=test/test-cases/secrules-language-tests/operators/ipMatch.json
TESTS+=test/test-cases/secrules-language-tests/operators/le.json
TESTS+=test/test-cases/secrules-language-tests/operators/lt.json
TESTS+=test/test-cases/secrules-language-tests/operators/noMatch.json
TESTS+=test/test-cases/secrules-language-tests/operators/pmFromFile.json
TESTS+=test/test-cases/secrules-language-tests/operators/pm.json
TESTS+=test/test-cases/secrules-language-tests/operators/rx.json
TESTS+=test/test-cases/secrules-language-tests/operators/rxGlobal.json
TESTS+=test/test-cases/secrules-language-tests/operators/streq.json
TESTS+=test/test-cases/secrules-language-tests/operators/strmatch.json
TESTS+=test/test-cases/secrules-language-tests/operators/unconditionalMatch.json
TESTS+=test/test-cases/secrules-language-tests/operators/validateByteRange.json
TESTS+=test/test-cases/secrules-language-tests/operators/validateUrlEncoding.json
TESTS+=test/test-cases/secrules-language-tests/operators/validateUtf8Encoding.json
TESTS+=test/test-cases/secrules-language-tests/operators/verifyCC.json
TESTS+=test/test-cases/secrules-language-tests/operators/verifycpf.json
TESTS+=test/test-cases/secrules-language-tests/operators/verifyssn.json
TESTS+=test/test-cases/secrules-language-tests/operators/verifysvnr.json
TESTS+=test/test-cases/secrules-language-tests/operators/within.json
TESTS+=test/test-cases/secrules-language-tests/transformations/base64DecodeExt.json
TESTS+=test/test-cases/secrules-language-tests/transformations/base64Decode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/base64Encode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/cmdLine.json
TESTS+=test/test-cases/secrules-language-tests/transformations/compressWhitespace.json
TESTS+=test/test-cases/secrules-language-tests/transformations/cssDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/escapeSeqDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/hexDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/hexEncode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/htmlEntityDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/jsDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/length.json
TESTS+=test/test-cases/secrules-language-tests/transformations/lowercase.json
TESTS+=test/test-cases/secrules-language-tests/transformations/md5.json
TESTS+=test/test-cases/secrules-language-tests/transformations/normalisePath.json
TESTS+=test/test-cases/secrules-language-tests/transformations/normalisePathWin.json
TESTS+=test/test-cases/secrules-language-tests/transformations/parityEven7bit.json
TESTS+=test/test-cases/secrules-language-tests/transformations/parityOdd7bit.json
TESTS+=test/test-cases/secrules-language-tests/transformations/parityZero7bit.json
TESTS+=test/test-cases/secrules-language-tests/transformations/removeCommentsChar.json
TESTS+=test/test-cases/secrules-language-tests/transformations/removeComments.json
TESTS+=test/test-cases/secrules-language-tests/transformations/removeNulls.json
TESTS+=test/test-cases/secrules-language-tests/transformations/removeWhitespace.json
TESTS+=test/test-cases/secrules-language-tests/transformations/replaceComments.json
TESTS+=test/test-cases/secrules-language-tests/transformations/replaceNulls.json
TESTS+=test/test-cases/secrules-language-tests/transformations/sha1.json
TESTS+=test/test-cases/secrules-language-tests/transformations/sqlHexDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/trim.json
TESTS+=test/test-cases/secrules-language-tests/transformations/trimLeft.json
TESTS+=test/test-cases/secrules-language-tests/transformations/trimRight.json
TESTS+=test/test-cases/secrules-language-tests/transformations/urlDecode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/urlDecodeUni.json
TESTS+=test/test-cases/secrules-language-tests/transformations/urlEncode.json
TESTS+=test/test-cases/secrules-language-tests/transformations/utf8toUnicode.json


pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = modsecurity.pc
EXTRA_DIST = modsecurity.pc.in \
             modsecurity.conf-recommended \
             unicode.mapping

