%skeleton "lalr1.cc" /* -*- C++ -*- */
%require "3.0.2"
%defines
%define parser_class_name {seclang_parser}
%define api.token.constructor
%define api.value.type variant
//%define api.namespace {modsecurity::yy}
%define parse.assert
%code requires
{
#include <string>
#include <iterator>

namespace ModSecurity {
namespace Parser {
class Driver;
}
}

#include "modsecurity/rule_unconditional.h"
#include "src/rule_script.h"

#include "src/actions/accuracy.h"
#include "src/actions/audit_log.h"
#include "src/actions/block.h"
#include "src/actions/capture.h"
#include "src/actions/chain.h"
#include "src/actions/ctl/audit_engine.h"
#include "src/actions/ctl/audit_log_parts.h"
#include "src/actions/ctl/request_body_access.h"
#include "src/actions/ctl/rule_engine.h"
#include "src/actions/ctl/request_body_processor_json.h"
#include "src/actions/ctl/request_body_processor_xml.h"
#include "src/actions/ctl/request_body_processor_urlencoded.h"
#include "src/actions/ctl/rule_remove_by_id.h"
#include "src/actions/ctl/rule_remove_by_tag.h"
#include "src/actions/ctl/rule_remove_target_by_id.h"
#include "src/actions/ctl/rule_remove_target_by_tag.h"
#include "src/actions/data/status.h"
#include "src/actions/disruptive/allow.h"
#include "src/actions/disruptive/deny.h"
#include "src/actions/disruptive/drop.h"
#include "src/actions/disruptive/pass.h"
#include "src/actions/disruptive/redirect.h"
#include "src/actions/init_col.h"
#include "src/actions/exec.h"
#include "src/actions/log_data.h"
#include "src/actions/log.h"
#include "src/actions/maturity.h"
#include "src/actions/msg.h"
#include "src/actions/multi_match.h"
#include "src/actions/no_audit_log.h"
#include "src/actions/no_log.h"
#include "src/actions/phase.h"
#include "src/actions/rev.h"
#include "src/actions/rule_id.h"
#include "src/actions/set_env.h"
#include "src/actions/set_rsc.h"
#include "src/actions/set_sid.h"
#include "src/actions/set_uid.h"
#include "src/actions/set_var.h"
#include "src/actions/severity.h"
#include "src/actions/skip_after.h"
#include "src/actions/skip.h"
#include "src/actions/tag.h"
#include "src/actions/ver.h"
#include "src/actions/xmlns.h"

#include "src/actions/transformations/none.h"
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/transformations/hex_encode.h"
#include "src/actions/transformations/parity_even_7bit.h"
#include "src/actions/transformations/utf8_to_unicode.h"
#include "src/actions/transformations/parity_zero_7bit.h"
#include "src/actions/transformations/sql_hex_decode.h"
#include "src/actions/transformations/replace_comments.h"
#include "src/actions/transformations/none.h"
#include "src/actions/transformations/url_decode.h"
#include "src/actions/transformations/lower_case.h"
#include "src/actions/transformations/upper_case.h"
#include "src/actions/transformations/hex_decode.h"
#include "src/actions/transformations/url_encode.h"
#include "src/actions/transformations/js_decode.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/transformations/parity_odd_7bit.h"
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/trim_right.h"
#include "src/actions/transformations/escape_seq_decode.h"
#include "src/actions/transformations/base64_decode_ext.h"
#include "src/actions/transformations/base64_decode.h"
#include "src/actions/transformations/trim.h"
#include "src/actions/transformations/cmd_line.h"
#include "src/actions/transformations/replace_nulls.h"
#include "src/actions/transformations/md5.h"
#include "src/actions/transformations/length.h"
#include "src/actions/transformations/sha1.h"
#include "src/actions/transformations/compress_whitespace.h"
#include "src/actions/transformations/normalise_path_win.h"
#include "src/actions/transformations/remove_nulls.h"
#include "src/actions/transformations/remove_comments.h"
#include "src/actions/transformations/normalise_path.h"
#include "src/actions/transformations/html_entity_decode.h"
#include "src/actions/transformations/trim_left.h"
#include "src/actions/transformations/remove_comments_char.h"
#include "src/actions/transformations/base64_encode.h"
#include "src/actions/transformations/remove_whitespace.h"
#include "src/actions/transformations/css_decode.h"

#include "src/operators/begins_with.h"
#include "src/operators/contains.h"
#include "src/operators/contains_word.h"
#include "src/operators/detect_sqli.h"
#include "src/operators/detect_xss.h"
#include "src/operators/ends_with.h"
#include "src/operators/eq.h"
#include "src/operators/fuzzy_hash.h"
#include "src/operators/ge.h"
#include "src/operators/geo_lookup.h"
#include "src/operators/gsblookup.h"
#include "src/operators/gt.h"
#include "src/operators/inspect_file.h"
#include "src/operators/ip_match_f.h"
#include "src/operators/ip_match_from_file.h"
#include "src/operators/ip_match.h"
#include "src/operators/le.h"
#include "src/operators/lt.h"
#include "src/operators/no_match.h"
#include "src/operators/operator.h"
#include "src/operators/pm_f.h"
#include "src/operators/pm_from_file.h"
#include "src/operators/pm.h"
#include "src/operators/rbl.h"
#include "src/operators/rsub.h"
#include "src/operators/rx.h"
#include "src/operators/rx_global.h"
#include "src/operators/str_eq.h"
#include "src/operators/str_match.h"
#include "src/operators/unconditional_match.h"
#include "src/operators/validate_byte_range.h"
#include "src/operators/validate_dtd.h"
#include "src/operators/validate_hash.h"
#include "src/operators/validate_schema.h"
#include "src/operators/validate_url_encoding.h"
#include "src/operators/validate_utf8_encoding.h"
#include "src/operators/verify_cc.h"
#include "src/operators/verify_cpf.h"
#include "src/operators/verify_ssn.h"
#include "src/operators/verify_svnr.h"
#include "src/operators/within.h"


#include "modsecurity/audit_log.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/rules_set_properties.h"
#include "modsecurity/rule.h"
#include "src/operators/operator.h"
#include "src/utils/geo_lookup.h"
#include "src/utils/string.h"
#include "src/utils/system.h"
#include "src/variables/args_combined_size.h"
#include "src/variables/args_get.h"
#include "src/variables/args_get_names.h"
#include "src/variables/args.h"
#include "src/variables/args_names.h"
#include "src/variables/args_post.h"
#include "src/variables/args_post_names.h"
#include "src/variables/auth_type.h"
#include "src/variables/duration.h"
#include "src/variables/env.h"
#include "src/variables/files_combined_size.h"
#include "src/variables/files.h"
#include "src/variables/files_names.h"
#include "src/variables/files_sizes.h"
#include "src/variables/files_tmp_content.h"
#include "src/variables/files_tmp_names.h"
#include "src/variables/full_request.h"
#include "src/variables/full_request_length.h"
#include "src/variables/geo.h"
#include "src/variables/highest_severity.h"
#include "src/variables/inbound_data_error.h"
#include "src/variables/matched_var.h"
#include "src/variables/matched_var_name.h"
#include "src/variables/matched_vars.h"
#include "src/variables/matched_vars_names.h"
#include "src/variables/modsec_build.h"
#include "src/variables/multipart_boundary_quoted.h"
#include "src/variables/multipart_boundary_whitespace.h"
#include "src/variables/multipart_crlf_lf_lines.h"
#include "src/variables/multipart_data_after.h"
#include "src/variables/multipart_data_before.h"
#include "src/variables/multipart_file_limit_exceeded.h"
#include "src/variables/multipart_file_name.h"
#include "src/variables/multipart_header_folding.h"
#include "src/variables/multipart_invalid_header_folding.h"
#include "src/variables/multipart_invalid_part.h"
#include "src/variables/multipart_invalid_quoting.h"
#include "src/variables/multipart_lf_line.h"
#include "src/variables/multipart_missing_semicolon.h"
#include "src/variables/multipart_name.h"
#include "src/variables/multipart_strict_error.h"
#include "src/variables/multipart_unmatched_boundary.h"
#include "src/variables/outbound_data_error.h"
#include "src/variables/path_info.h"
#include "src/variables/query_string.h"
#include "src/variables/remote_addr.h"
#include "src/variables/remote_host.h"
#include "src/variables/remote_port.h"
#include "src/variables/remote_user.h"
#include "src/variables/reqbody_error.h"
#include "src/variables/reqbody_error_msg.h"
#include "src/variables/reqbody_processor_error.h"
#include "src/variables/reqbody_processor_error_msg.h"
#include "src/variables/reqbody_processor.h"
#include "src/variables/request_base_name.h"
#include "src/variables/request_body.h"
#include "src/variables/request_body_length.h"
#include "src/variables/request_cookies.h"
#include "src/variables/request_cookies_names.h"
#include "src/variables/multipart_part_headers.h"
#include "src/variables/request_file_name.h"
#include "src/variables/request_headers.h"
#include "src/variables/request_headers_names.h"
#include "src/variables/request_line.h"
#include "src/variables/request_method.h"
#include "src/variables/request_protocol.h"
#include "src/variables/request_uri.h"
#include "src/variables/request_uri_raw.h"
#include "src/variables/resource.h"
#include "src/variables/response_body.h"
#include "src/variables/response_content_length.h"
#include "src/variables/response_content_type.h"
#include "src/variables/response_headers.h"
#include "src/variables/response_headers_names.h"
#include "src/variables/response_protocol.h"
#include "src/variables/response_status.h"
#include "src/variables/rule.h"
#include "src/variables/server_addr.h"
#include "src/variables/server_name.h"
#include "src/variables/server_port.h"
#include "src/variables/session_id.h"
#include "src/variables/web_app_id.h"
#include "src/variables/time_day.h"
#include "src/variables/time_epoch.h"
#include "src/variables/time.h"
#include "src/variables/time_hour.h"
#include "src/variables/time_min.h"
#include "src/variables/time_mon.h"
#include "src/variables/time_sec.h"
#include "src/variables/time_wday.h"
#include "src/variables/time_year.h"
#include "src/variables/tx.h"
#include "src/variables/unique_id.h"
#include "src/variables/url_encoded_error.h"
#include "src/variables/user.h"
#include "src/variables/user_id.h"
#include "src/variables/variable.h"
#include "src/variables/xml.h"
#include "src/variables/ip.h"
#include "src/variables/global.h"
#include "src/variables/session.h"
#include "src/variables/status.h"

using namespace modsecurity;
using namespace modsecurity::variables;
using namespace modsecurity::Utils;
using namespace modsecurity::operators;


#define CHECK_VARIATION_DECL \
    Variable *var = NULL; \
    bool t = false;

#define CHECK_VARIATION(a) \
    if (var == NULL) { \
        if (name.at(0) == std::string(#a).at(0)) { \
            name.erase(0, 1); \
            t = true ; \
        } \
    } else { \
        t = false; \
    } \
    if (t)


#define ACTION_NOT_SUPPORTED(a, b) \
    driver.error(b, "Action: " + std::string(a) + " is not yet supported."); \
    YYERROR;


#define OPERATOR_NOT_SUPPORTED(a, b) \
    driver.error(b, "Operator: " + std::string(a) + " is not yet supported."); \
    YYERROR;


#define ACTION_INIT(a, b) \
    std::string error; \
    if (a->init(&error) == false) { \
        driver.error(b, error); \
        YYERROR; \
    }

#define OPERATOR_CONTAINER(a, b) \
    std::unique_ptr<Operator> c(b); \
    a = std::move(c);

#define ACTION_CONTAINER(a, b) \
    std::unique_ptr<actions::Action> c(b); \
    a = std::move(c);

#define VARIABLE_CONTAINER(a, b) \
    std::unique_ptr<Variable> c(b); \
    a = std::move(c);

}
// The parsing context.
%param { modsecurity::Parser::Driver& driver }
%locations
%initial-action
{
  // Initialize the initial location.
  driver.m_filenames.push_back(driver.file);
  @$.begin.filename = @$.end.filename = &(driver.m_filenames.back());
};
%define parse.trace
%define parse.error verbose
%code
{
#include "src/parser/driver.h"
}
%define api.token.prefix {TOK_}
%token
  END  0  "end of file"
  COMMA    ","
  CONFIG_CONTENT_INJECTION                     "CONFIG_CONTENT_INJECTION"
  CONGIG_DIR_RESPONSE_BODY_MP_CLEAR            "CONGIG_DIR_RESPONSE_BODY_MP_CLEAR"
  PIPE
  NEW_LINE
  VAR_COUNT
  VAR_EXCLUSION
  VARIABLE_ARGS
  VARIABLE_ARGS_POST
  VARIABLE_ARGS_GET
  VARIABLE_FILES_SIZES
  VARIABLE_FILES_NAMES
  VARIABLE_FILES_TMP_CONTENT
  VARIABLE_MULTIPART_FILENAME
  VARIABLE_MULTIPART_NAME
  VARIABLE_MATCHED_VARS_NAMES
  VARIABLE_MATCHED_VARS
  VARIABLE_FILES
  VARIABLE_REQUEST_COOKIES
  VARIABLE_REQUEST_HEADERS
  VARIABLE_RESPONSE_HEADERS
  VARIABLE_GEO
  VARIABLE_REQUEST_COOKIES_NAMES
  VARIABLE_MULTIPART_PART_HEADERS
  VARIABLE_ARGS_COMBINED_SIZE
  VARIABLE_ARGS_GET_NAMES
  VARIABLE_RULE
  VARIABLE_ARGS_NAMES           "Variable ARGS_NAMES"
  VARIABLE_ARGS_POST_NAMES
  VARIABLE_AUTH_TYPE            "AUTH_TYPE"
  VARIABLE_FILES_COMBINED_SIZE  "FILES_COMBINED_SIZE"
  VARIABLE_FILES_TMP_NAMES       "FILES_TMPNAMES"
  VARIABLE_FULL_REQUEST         "FULL_REQUEST"
  VARIABLE_FULL_REQUEST_LENGTH  "FULL_REQUEST_LENGTH"
  VARIABLE_INBOUND_DATA_ERROR   "INBOUND_DATA_ERROR"
  VARIABLE_MATCHED_VAR          "MATCHED_VAR"
  VARIABLE_MATCHED_VAR_NAME     "MATCHED_VAR_NAME"
  VARIABLE_MULTIPART_BOUNDARY_QUOTED
  VARIABLE_MULTIPART_BOUNDARY_WHITESPACE
  VARIABLE_MULTIPART_CRLF_LF_LINES    "MULTIPART_CRLF_LF_LINES"
  VARIABLE_MULTIPART_DATA_AFTER "MULTIPART_DATA_AFTER"
  VARIABLE_MULTIPART_DATA_BEFORE
  VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED       "MULTIPART_FILE_LIMIT_EXCEEDED"
  VARIABLE_MULTIPART_HEADER_FOLDING            "MULTIPART_HEADER_FOLDING"
  VARIABLE_MULTIPART_INVALID_HEADER_FOLDING    "MULTIPART_INVALID_HEADER_FOLDING"
  VARIABLE_MULTIPART_INVALID_PART
  VARIABLE_MULTIPART_INVALID_QUOTING           "MULTIPART_INVALID_QUOTING"
  VARIABLE_MULTIPART_LF_LINE
  VARIABLE_MULTIPART_MISSING_SEMICOLON
  VARIABLE_MULTIPART_SEMICOLON_MISSING
  VARIABLE_MULTIPART_STRICT_ERROR              "MULTIPART_STRICT_ERROR"
  VARIABLE_MULTIPART_UNMATCHED_BOUNDARY        "MULTIPART_UNMATCHED_BOUNDARY"
  VARIABLE_OUTBOUND_DATA_ERROR  "OUTBOUND_DATA_ERROR"
  VARIABLE_PATH_INFO            "PATH_INFO"
  VARIABLE_QUERY_STRING         "QUERY_STRING"
  VARIABLE_REMOTE_ADDR          "REMOTE_ADDR"
  VARIABLE_REMOTE_HOST          "REMOTE_HOST"
  VARIABLE_REMOTE_PORT          "REMOTE_PORT"
  VARIABLE_REQBODY_ERROR_MSG    "REQBODY_ERROR_MSG"
  VARIABLE_REQBODY_ERROR        "REQBODY_ERROR"
  VARIABLE_REQBODY_PROCESSOR_ERROR_MSG    "REQBODY_PROCESSOR_ERROR_MSG"
  VARIABLE_REQBODY_PROCESSOR_ERROR        "REQBODY_PROCESSOR_ERROR"
  VARIABLE_REQBODY_PROCESSOR    "REQBODY_PROCESSOR"
  VARIABLE_REQUEST_BASENAME     "REQUEST_BASENAME"
  VARIABLE_REQUEST_BODY_LENGTH  "REQUEST_BODY_LENGTH"
  VARIABLE_REQUEST_BODY         "REQUEST_BODY"
  VARIABLE_REQUEST_FILE_NAME     "REQUEST_FILENAME"
  VARIABLE_REQUEST_HEADERS_NAMES
  VARIABLE_REQUEST_LINE         "REQUEST_LINE"
  VARIABLE_REQUEST_METHOD       "REQUEST_METHOD"
  VARIABLE_REQUEST_PROTOCOL     "REQUEST_PROTOCOL"
  VARIABLE_REQUEST_URI_RAW      "REQUEST_URI_RAW"
  VARIABLE_REQUEST_URI          "REQUEST_URI"
  VARIABLE_RESOURCE             "RESOURCE"
  VARIABLE_RESPONSE_BODY        "RESPONSE_BODY"
  VARIABLE_RESPONSE_CONTENT_LENGTH    "RESPONSE_CONTENT_LENGTH"
  VARIABLE_RESPONSE_CONTENT_TYPE
  VARIABLE_RESPONSE_HEADERS_NAMES
  VARIABLE_RESPONSE_PROTOCOL    "RESPONSE_PROTOCOL"
  VARIABLE_RESPONSE_STATUS      "RESPONSE_STATUS"
  VARIABLE_SERVER_ADDR          "SERVER_ADDR"
  VARIABLE_SERVER_NAME          "SERVER_NAME"
  VARIABLE_SERVER_PORT          "SERVER_PORT"
  VARIABLE_SESSION_ID           "SESSIONID"
  VARIABLE_UNIQUE_ID            "UNIQUE_ID"
  VARIABLE_URL_ENCODED_ERROR    "URLENCODED_ERROR"
  VARIABLE_USER_ID               "USERID"
  VARIABLE_WEB_APP_ID           "WEBAPPID"


  VARIABLE_STATUS                              "VARIABLE_STATUS"
  VARIABLE_STATUS_LINE                         "VARIABLE_STATUS_LINE"
  VARIABLE_IP                                  "VARIABLE_IP"
  VARIABLE_GLOBAL                              "VARIABLE_GLOBAL"
  VARIABLE_TX                                  "VARIABLE_TX"
  VARIABLE_SESSION                             "VARIABLE_SESSION"
  VARIABLE_USER                                "VARIABLE_USER"
  RUN_TIME_VAR_ENV                             "RUN_TIME_VAR_ENV"
  RUN_TIME_VAR_XML                             "RUN_TIME_VAR_XML"

  ACTION_SETVAR                                "SetVar"
  SETVAR_OPERATION_EQUALS
  SETVAR_OPERATION_EQUALS_PLUS
  SETVAR_OPERATION_EQUALS_MINUS
  NOT                                          "NOT"

  OPERATOR_BEGINS_WITH                         "OPERATOR_BEGINS_WITH"
  OPERATOR_CONTAINS                            "OPERATOR_CONTAINS"
  OPERATOR_CONTAINS_WORD                       "OPERATOR_CONTAINS_WORD"
  OPERATOR_DETECT_SQLI                         "OPERATOR_DETECT_SQLI"
  OPERATOR_DETECT_XSS                          "OPERATOR_DETECT_XSS"
  OPERATOR_ENDS_WITH                           "OPERATOR_ENDS_WITH"
  OPERATOR_EQ                                  "OPERATOR_EQ"
  OPERATOR_FUZZY_HASH                          "OPERATOR_FUZZY_HASH"
  OPERATOR_GEOLOOKUP                           "OPERATOR_GEOLOOKUP"
  OPERATOR_GE                                  "OPERATOR_GE"
  OPERATOR_GSB_LOOKUP                          "OPERATOR_GSB_LOOKUP"
  OPERATOR_GT                                  "OPERATOR_GT"
  OPERATOR_INSPECT_FILE                        "OPERATOR_INSPECT_FILE"
  OPERATOR_IP_MATCH_FROM_FILE                  "OPERATOR_IP_MATCH_FROM_FILE"
  OPERATOR_IP_MATCH                            "OPERATOR_IP_MATCH"
  OPERATOR_LE                                  "OPERATOR_LE"
  OPERATOR_LT                                  "OPERATOR_LT"
  OPERATOR_PM_FROM_FILE                        "OPERATOR_PM_FROM_FILE"
  OPERATOR_PM                                  "OPERATOR_PM"
  OPERATOR_RBL                                 "OPERATOR_RBL"
  OPERATOR_RSUB                                "OPERATOR_RSUB"
  OPERATOR_RX_CONTENT_ONLY                     "Operator RX (content only)"
  OPERATOR_RX                                  "OPERATOR_RX"
  OPERATOR_RX_GLOBAL                           "OPERATOR_RX_GLOBAL"
  OPERATOR_STR_EQ                              "OPERATOR_STR_EQ"
  OPERATOR_STR_MATCH                           "OPERATOR_STR_MATCH"
  OPERATOR_UNCONDITIONAL_MATCH                 "OPERATOR_UNCONDITIONAL_MATCH"
  OPERATOR_VALIDATE_BYTE_RANGE                 "OPERATOR_VALIDATE_BYTE_RANGE"
  OPERATOR_VALIDATE_DTD                        "OPERATOR_VALIDATE_DTD"
  OPERATOR_VALIDATE_HASH                       "OPERATOR_VALIDATE_HASH"
  OPERATOR_VALIDATE_SCHEMA                     "OPERATOR_VALIDATE_SCHEMA"
  OPERATOR_VALIDATE_URL_ENCODING               "OPERATOR_VALIDATE_URL_ENCODING"
  OPERATOR_VALIDATE_UTF8_ENCODING              "OPERATOR_VALIDATE_UTF8_ENCODING"
  OPERATOR_VERIFY_CC                           "OPERATOR_VERIFY_CC"
  OPERATOR_VERIFY_CPF                          "OPERATOR_VERIFY_CPF"
  OPERATOR_VERIFY_SSN                          "OPERATOR_VERIFY_SSN"
  OPERATOR_VERIFY_SVNR                          "OPERATOR_VERIFY_SVNR"
  OPERATOR_WITHIN                              "OPERATOR_WITHIN"

  CONFIG_DIR_AUDIT_LOG_FMT
  JSON
  NATIVE

  ACTION_CTL_RULE_ENGINE                       "ACTION_CTL_RULE_ENGINE"
;

%token <std::string>
  ACTION_ACCURACY                              "Accuracy"
  ACTION_ALLOW                                 "Allow"
  ACTION_APPEND                                "Append"
  ACTION_AUDIT_LOG                             "AuditLog"
  ACTION_BLOCK                                 "Block"
  ACTION_CAPTURE                               "Capture"
  ACTION_CHAIN                                 "Chain"
  ACTION_CTL_AUDIT_ENGINE                      "ACTION_CTL_AUDIT_ENGINE"
  ACTION_CTL_AUDIT_LOG_PARTS                   "ACTION_CTL_AUDIT_LOG_PARTS"
  ACTION_CTL_BDY_JSON                          "ACTION_CTL_BDY_JSON"
  ACTION_CTL_BDY_XML                           "ACTION_CTL_BDY_XML"
  ACTION_CTL_BDY_URLENCODED                    "ACTION_CTL_BDY_URLENCODED"
  ACTION_CTL_FORCE_REQ_BODY_VAR                "ACTION_CTL_FORCE_REQ_BODY_VAR"
  ACTION_CTL_REQUEST_BODY_ACCESS               "ACTION_CTL_REQUEST_BODY_ACCESS"
  ACTION_CTL_RULE_REMOVE_BY_ID                 "ACTION_CTL_RULE_REMOVE_BY_ID"
  ACTION_CTL_RULE_REMOVE_BY_TAG                "ACTION_CTL_RULE_REMOVE_BY_TAG"
  ACTION_CTL_RULE_REMOVE_TARGET_BY_ID          "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
  ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG         "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
  ACTION_DENY                                  "Deny"
  ACTION_DEPRECATE_VAR                         "DeprecateVar"
  ACTION_DROP                                  "Drop"
  ACTION_EXEC                                  "Exec"
  ACTION_EXPIRE_VAR                            "ExpireVar"
  ACTION_ID                                    "Id"
  ACTION_INITCOL                               "InitCol"
  ACTION_LOG                                   "Log"
  ACTION_LOG_DATA                              "LogData"
  ACTION_MATURITY                              "Maturity"
  ACTION_MSG                                   "Msg"
  ACTION_MULTI_MATCH                           "MultiMatch"
  ACTION_NO_AUDIT_LOG                          "NoAuditLog"
  ACTION_NO_LOG                                "NoLog"
  ACTION_PASS                                  "Pass"
  ACTION_PAUSE                                 "Pause"
  ACTION_PHASE                                 "Phase"
  ACTION_PREPEND                               "Prepend"
  ACTION_PROXY                                 "Proxy"
  ACTION_REDIRECT                              "Redirect"
  ACTION_REV                                   "Rev"
  ACTION_SANITISE_ARG                          "SanitiseArg"
  ACTION_SANITISE_MATCHED                      "SanitiseMatched"
  ACTION_SANITISE_MATCHED_BYTES                "SanitiseMatchedBytes"
  ACTION_SANITISE_REQUEST_HEADER               "SanitiseRequestHeader"
  ACTION_SANITISE_RESPONSE_HEADER              "SanitiseResponseHeader"
  ACTION_SETENV                                "SetEnv"
  ACTION_SETRSC                                "SetRsc"
  ACTION_SETSID                                "SetSid"
  ACTION_SETUID                                "SetUID"
  ACTION_SEVERITY                              "Severity"
  ACTION_SKIP                                  "Skip"
  ACTION_SKIP_AFTER                            "SkipAfter"
  ACTION_STATUS                                "Status"
  ACTION_TAG                                   "Tag"
  ACTION_TRANSFORMATION_BASE_64_ENCODE         "ACTION_TRANSFORMATION_BASE_64_ENCODE"
  ACTION_TRANSFORMATION_BASE_64_DECODE         "ACTION_TRANSFORMATION_BASE_64_DECODE"
  ACTION_TRANSFORMATION_BASE_64_DECODE_EXT     "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
  ACTION_TRANSFORMATION_CMD_LINE               "ACTION_TRANSFORMATION_CMD_LINE"
  ACTION_TRANSFORMATION_COMPRESS_WHITESPACE    "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
  ACTION_TRANSFORMATION_CSS_DECODE             "ACTION_TRANSFORMATION_CSS_DECODE"
  ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE      "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
  ACTION_TRANSFORMATION_HEX_ENCODE             "ACTION_TRANSFORMATION_HEX_ENCODE"
  ACTION_TRANSFORMATION_HEX_DECODE             "ACTION_TRANSFORMATION_HEX_DECODE"
  ACTION_TRANSFORMATION_HTML_ENTITY_DECODE     "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
  ACTION_TRANSFORMATION_JS_DECODE              "ACTION_TRANSFORMATION_JS_DECODE"
  ACTION_TRANSFORMATION_LENGTH                 "ACTION_TRANSFORMATION_LENGTH"
  ACTION_TRANSFORMATION_LOWERCASE              "ACTION_TRANSFORMATION_LOWERCASE"
  ACTION_TRANSFORMATION_MD5                    "ACTION_TRANSFORMATION_MD5"
  ACTION_TRANSFORMATION_NONE                   "ACTION_TRANSFORMATION_NONE"
  ACTION_TRANSFORMATION_NORMALISE_PATH         "ACTION_TRANSFORMATION_NORMALISE_PATH"
  ACTION_TRANSFORMATION_NORMALISE_PATH_WIN     "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
  ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT      "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
  ACTION_TRANSFORMATION_PARITY_ODD_7_BIT       "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
  ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT      "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
  ACTION_TRANSFORMATION_REMOVE_COMMENTS        "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
  ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR   "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
  ACTION_TRANSFORMATION_REMOVE_NULLS           "ACTION_TRANSFORMATION_REMOVE_NULLS"
  ACTION_TRANSFORMATION_REMOVE_WHITESPACE      "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
  ACTION_TRANSFORMATION_REPLACE_COMMENTS       "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
  ACTION_TRANSFORMATION_REPLACE_NULLS          "ACTION_TRANSFORMATION_REPLACE_NULLS"
  ACTION_TRANSFORMATION_SHA1                   "ACTION_TRANSFORMATION_SHA1"
  ACTION_TRANSFORMATION_SQL_HEX_DECODE         "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
  ACTION_TRANSFORMATION_TRIM                   "ACTION_TRANSFORMATION_TRIM"
  ACTION_TRANSFORMATION_TRIM_LEFT              "ACTION_TRANSFORMATION_TRIM_LEFT"
  ACTION_TRANSFORMATION_TRIM_RIGHT             "ACTION_TRANSFORMATION_TRIM_RIGHT"
  ACTION_TRANSFORMATION_UPPERCASE              "ACTION_TRANSFORMATION_UPPERCASE"
  ACTION_TRANSFORMATION_URL_ENCODE             "ACTION_TRANSFORMATION_URL_ENCODE"
  ACTION_TRANSFORMATION_URL_DECODE             "ACTION_TRANSFORMATION_URL_DECODE"
  ACTION_TRANSFORMATION_URL_DECODE_UNI         "ACTION_TRANSFORMATION_URL_DECODE_UNI"
  ACTION_TRANSFORMATION_UTF8_TO_UNICODE        "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
  ACTION_VER                                   "Ver"
  ACTION_XMLNS                                 "xmlns"
  CONFIG_COMPONENT_SIG                         "CONFIG_COMPONENT_SIG"
  CONFIG_CONN_ENGINE                           "CONFIG_CONN_ENGINE"
  CONFIG_SEC_ARGUMENT_SEPARATOR                "CONFIG_SEC_ARGUMENT_SEPARATOR"
  CONFIG_SEC_WEB_APP_ID                        "CONFIG_SEC_WEB_APP_ID"
  CONFIG_SEC_SERVER_SIG                        "CONFIG_SEC_SERVER_SIG"
  CONFIG_DIR_AUDIT_DIR                         "CONFIG_DIR_AUDIT_DIR"
  CONFIG_DIR_AUDIT_DIR_MOD                     "CONFIG_DIR_AUDIT_DIR_MOD"
  CONFIG_DIR_AUDIT_ENG                         "CONFIG_DIR_AUDIT_ENG"
  CONFIG_DIR_AUDIT_FLE_MOD                     "CONFIG_DIR_AUDIT_FLE_MOD"
  CONFIG_DIR_AUDIT_LOG                         "CONFIG_DIR_AUDIT_LOG"
  CONFIG_DIR_AUDIT_LOG2                        "CONFIG_DIR_AUDIT_LOG2"
  CONFIG_DIR_AUDIT_LOG_P                       "CONFIG_DIR_AUDIT_LOG_P"
  CONFIG_DIR_AUDIT_STS                         "CONFIG_DIR_AUDIT_STS"
  CONFIG_DIR_AUDIT_TPE                         "CONFIG_DIR_AUDIT_TPE"
  CONFIG_DIR_DEBUG_LOG                         "CONFIG_DIR_DEBUG_LOG"
  CONFIG_DIR_DEBUG_LVL                         "CONFIG_DIR_DEBUG_LVL"
  CONFIG_SEC_CACHE_TRANSFORMATIONS             "CONFIG_SEC_CACHE_TRANSFORMATIONS"
  CONFIG_SEC_DISABLE_BACKEND_COMPRESS          "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
  CONFIG_SEC_HASH_ENGINE                       "CONFIG_SEC_HASH_ENGINE"
  CONFIG_SEC_HASH_KEY                          "CONFIG_SEC_HASH_KEY"
  CONFIG_SEC_HASH_PARAM                        "CONFIG_SEC_HASH_PARAM"
  CONFIG_SEC_HASH_METHOD_RX                    "CONFIG_SEC_HASH_METHOD_RX"
  CONFIG_SEC_HASH_METHOD_PM                    "CONFIG_SEC_HASH_METHOD_PM"
  CONFIG_SEC_CHROOT_DIR                        "CONFIG_SEC_CHROOT_DIR"
  CONFIG_DIR_GEO_DB                            "CONFIG_DIR_GEO_DB"
  CONFIG_DIR_GSB_DB                            "CONFIG_DIR_GSB_DB"
  CONFIG_SEC_GUARDIAN_LOG                      "CONFIG_SEC_GUARDIAN_LOG"
  CONFIG_DIR_PCRE_MATCH_LIMIT                  "CONFIG_DIR_PCRE_MATCH_LIMIT"
  CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION        "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
  CONFIG_SEC_CONN_R_STATE_LIMIT                "CONFIG_SEC_CONN_R_STATE_LIMIT"
  CONFIG_SEC_CONN_W_STATE_LIMIT                "CONFIG_SEC_CONN_W_STATE_LIMIT"
  CONFIG_SEC_SENSOR_ID                         "CONFIG_SEC_SENSOR_ID"
  CONFIG_DIR_ARGS_LIMIT                        "CONFIG_DIR_ARGS_LIMIT"
  CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT         "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
  CONFIG_DIR_REQ_BODY                          "CONFIG_DIR_REQ_BODY"
  CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT          "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
  CONFIG_DIR_REQ_BODY_LIMIT                    "CONFIG_DIR_REQ_BODY_LIMIT"
  CONFIG_DIR_REQ_BODY_LIMIT_ACTION             "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
  CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT           "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
  CONFIG_DIR_RES_BODY                          "CONFIG_DIR_RES_BODY"
  CONFIG_DIR_RES_BODY_LIMIT                    "CONFIG_DIR_RES_BODY_LIMIT"
  CONFIG_DIR_RES_BODY_LIMIT_ACTION             "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
  CONFIG_SEC_RULE_INHERITANCE                  "CONFIG_SEC_RULE_INHERITANCE"
  CONFIG_SEC_RULE_PERF_TIME                    "CONFIG_SEC_RULE_PERF_TIME"
  CONFIG_DIR_RULE_ENG                          "CONFIG_DIR_RULE_ENG"
  CONFIG_DIR_SEC_ACTION                        "CONFIG_DIR_SEC_ACTION"
  CONFIG_DIR_SEC_DEFAULT_ACTION                "CONFIG_DIR_SEC_DEFAULT_ACTION"
  CONFIG_DIR_SEC_MARKER                        "CONFIG_DIR_SEC_MARKER"
  CONFIG_DIR_UNICODE_MAP_FILE                  "CONFIG_DIR_UNICODE_MAP_FILE"
  CONFIG_DIR_UNICODE_CODE_PAGE                 "CONFIG_DIR_UNICODE_CODE_PAGE"
  CONFIG_SEC_COLLECTION_TIMEOUT                "CONFIG_SEC_COLLECTION_TIMEOUT"
  CONFIG_SEC_HTTP_BLKEY                        "CONFIG_SEC_HTTP_BLKEY"
  CONFIG_SEC_INTERCEPT_ON_ERROR                "CONFIG_SEC_INTERCEPT_ON_ERROR"
  CONFIG_SEC_REMOTE_RULES_FAIL_ACTION          "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
  CONFIG_SEC_RULE_REMOVE_BY_ID                 "CONFIG_SEC_RULE_REMOVE_BY_ID"
  CONFIG_SEC_RULE_REMOVE_BY_MSG                "CONFIG_SEC_RULE_REMOVE_BY_MSG"
  CONFIG_SEC_RULE_REMOVE_BY_TAG                "CONFIG_SEC_RULE_REMOVE_BY_TAG"
  CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG         "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
  CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG         "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
  CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID          "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
  CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID          "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
  CONFIG_UPDLOAD_KEEP_FILES                    "CONFIG_UPDLOAD_KEEP_FILES"
  CONFIG_UPDLOAD_SAVE_TMP_FILES                "CONFIG_UPDLOAD_SAVE_TMP_FILES"
  CONFIG_UPLOAD_DIR                            "CONFIG_UPLOAD_DIR"
  CONFIG_UPLOAD_FILE_LIMIT                     "CONFIG_UPLOAD_FILE_LIMIT"
  CONFIG_UPLOAD_FILE_MODE                      "CONFIG_UPLOAD_FILE_MODE"
  CONFIG_VALUE_ABORT                           "CONFIG_VALUE_ABORT"
  CONFIG_VALUE_DETC                            "CONFIG_VALUE_DETC"
  CONFIG_VALUE_HTTPS                           "CONFIG_VALUE_HTTPS"
  CONFIG_VALUE_OFF                             "CONFIG_VALUE_OFF"
  CONFIG_VALUE_ON                              "CONFIG_VALUE_ON"
  CONFIG_VALUE_PARALLEL                        "CONFIG_VALUE_PARALLEL"
  CONFIG_VALUE_PROCESS_PARTIAL                 "CONFIG_VALUE_PROCESS_PARTIAL"
  CONFIG_VALUE_REJECT                          "CONFIG_VALUE_REJECT"
  CONFIG_VALUE_RELEVANT_ONLY                   "CONFIG_VALUE_RELEVANT_ONLY"
  CONFIG_VALUE_SERIAL                          "CONFIG_VALUE_SERIAL"
  CONFIG_VALUE_WARN                            "CONFIG_VALUE_WARN"
  CONFIG_XML_EXTERNAL_ENTITY                   "CONFIG_XML_EXTERNAL_ENTITY"
  CONGIG_DIR_RESPONSE_BODY_MP                  "CONGIG_DIR_RESPONSE_BODY_MP"
  CONGIG_DIR_SEC_ARG_SEP                       "CONGIG_DIR_SEC_ARG_SEP"
  CONGIG_DIR_SEC_COOKIE_FORMAT                 "CONGIG_DIR_SEC_COOKIE_FORMAT"
  CONFIG_SEC_COOKIEV0_SEPARATOR                "CONFIG_SEC_COOKIEV0_SEPARATOR"
  CONGIG_DIR_SEC_DATA_DIR                      "CONGIG_DIR_SEC_DATA_DIR"
  CONGIG_DIR_SEC_STATUS_ENGINE                 "CONGIG_DIR_SEC_STATUS_ENGINE"
  CONFIG_SEC_STREAM_IN_BODY_INSPECTION         "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
  CONFIG_SEC_STREAM_OUT_BODY_INSPECTION        "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
  CONGIG_DIR_SEC_TMP_DIR                       "CONGIG_DIR_SEC_TMP_DIR"
  DIRECTIVE                                    "DIRECTIVE"
  DIRECTIVE_SECRULESCRIPT                      "DIRECTIVE_SECRULESCRIPT"
  FREE_TEXT_QUOTE_MACRO_EXPANSION              "FREE_TEXT_QUOTE_MACRO_EXPANSION"
  QUOTATION_MARK                               "QUOTATION_MARK"
  RUN_TIME_VAR_BLD                             "RUN_TIME_VAR_BLD"
  RUN_TIME_VAR_DUR                             "RUN_TIME_VAR_DUR"
  RUN_TIME_VAR_HSV                             "RUN_TIME_VAR_HSV"
  RUN_TIME_VAR_REMOTE_USER                     "RUN_TIME_VAR_REMOTE_USER"
  RUN_TIME_VAR_TIME                            "RUN_TIME_VAR_TIME"
  RUN_TIME_VAR_TIME_DAY                        "RUN_TIME_VAR_TIME_DAY"
  RUN_TIME_VAR_TIME_EPOCH                      "RUN_TIME_VAR_TIME_EPOCH"
  RUN_TIME_VAR_TIME_HOUR                       "RUN_TIME_VAR_TIME_HOUR"
  RUN_TIME_VAR_TIME_MIN                        "RUN_TIME_VAR_TIME_MIN"
  RUN_TIME_VAR_TIME_MON                        "RUN_TIME_VAR_TIME_MON"
  RUN_TIME_VAR_TIME_SEC                        "RUN_TIME_VAR_TIME_SEC"
  RUN_TIME_VAR_TIME_WDAY                       "RUN_TIME_VAR_TIME_WDAY"
  RUN_TIME_VAR_TIME_YEAR                       "RUN_TIME_VAR_TIME_YEAR"
  VARIABLE                                     "VARIABLE"
  DICT_ELEMENT                                 "Dictionary element"
  DICT_ELEMENT_WITH_EQUALS                     "Dictionary element, with equals"
  DICT_ELEMENT_REGEXP                          "Dictionary element, selected by regexp"
;

%type <std::unique_ptr<actions::Action>> act

%type <std::unique_ptr<actions::Action>> setvar_action
%type <std::unique_ptr<RunTimeString>>   run_time_string

%type <std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > >
  actions_may_quoted
  actions
;

%type <std::unique_ptr<Operator>>
  op_before_init
  op
;

%type <std::unique_ptr<std::vector<std::unique_ptr<Variable> > > > variables_pre_process
%type <std::unique_ptr<std::vector<std::unique_ptr<Variable> > > > variables_may_be_quoted
%type <std::unique_ptr<std::vector<std::unique_ptr<Variable> > > > variables
%type <std::unique_ptr<Variable>> var


//%printer { yyoutput << $$; } <*>;

%%
%start input;


input:
    END
      {
        return 0;
      }
    | input line
    | line
    ;

line: expression
    ;

audit_log:
    /* SecAuditLogDirMode */
    CONFIG_DIR_AUDIT_DIR_MOD
      {
        driver.m_auditLog->setStorageDirMode(strtol($1.c_str(), NULL, 8));
      }

    /* SecAuditLogStorageDir */
    | CONFIG_DIR_AUDIT_DIR
      {
        driver.m_auditLog->setStorageDir($1);
      }

    /* SecAuditEngine */
    | CONFIG_DIR_AUDIT_ENG CONFIG_VALUE_RELEVANT_ONLY
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::RelevantOnlyAuditLogStatus);
      }
    | CONFIG_DIR_AUDIT_ENG CONFIG_VALUE_OFF
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OffAuditLogStatus);
      }
    | CONFIG_DIR_AUDIT_ENG CONFIG_VALUE_ON
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OnAuditLogStatus);
      }

    /* SecAuditLogFileMode */
    | CONFIG_DIR_AUDIT_FLE_MOD
      {
        driver.m_auditLog->setFileMode(strtol($1.c_str(), NULL, 8));
      }

    /* SecAuditLog2 */
    | CONFIG_DIR_AUDIT_LOG2
      {
        driver.m_auditLog->setFilePath2($1);
      }

    /* SecAuditLogParts */
    | CONFIG_DIR_AUDIT_LOG_P
      {
        driver.m_auditLog->setParts($1);
      }

    /* SecAuditLog */
    | CONFIG_DIR_AUDIT_LOG
      {
        driver.m_auditLog->setFilePath1($1);
      }

    | CONFIG_DIR_AUDIT_LOG_FMT JSON
      {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::JSONAuditLogFormat);
      }

    | CONFIG_DIR_AUDIT_LOG_FMT NATIVE
      {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::NativeAuditLogFormat);
      }

    /* SecAuditLogRelevantStatus */
    | CONFIG_DIR_AUDIT_STS
      {
        std::string relevant_status($1);
        driver.m_auditLog->setRelevantStatus(relevant_status);
      }

    /* SecAuditLogType */
    | CONFIG_DIR_AUDIT_TPE CONFIG_VALUE_SERIAL
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::SerialAuditLogType);
      }
    | CONFIG_DIR_AUDIT_TPE CONFIG_VALUE_PARALLEL
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::ParallelAuditLogType);
      }
    | CONFIG_DIR_AUDIT_TPE CONFIG_VALUE_HTTPS
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::HttpsAuditLogType);
      }

    /* Upload */
    | CONFIG_UPDLOAD_KEEP_FILES CONFIG_VALUE_ON
      {
        driver.m_uploadKeepFiles = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
    | CONFIG_UPDLOAD_KEEP_FILES CONFIG_VALUE_OFF
      {
        driver.m_uploadKeepFiles = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
    | CONFIG_UPDLOAD_KEEP_FILES CONFIG_VALUE_RELEVANT_ONLY
      {
        driver.error(@0, "SecUploadKeepFiles RelevantOnly is not currently supported. Accepted values are On or Off");
        YYERROR;
      }
    | CONFIG_UPLOAD_FILE_LIMIT
      {
        driver.m_uploadFileLimit.m_set = true;
        driver.m_uploadFileLimit.m_value = strtol($1.c_str(), NULL, 10);
      }
    | CONFIG_UPLOAD_FILE_MODE
      {
        driver.m_uploadFileMode.m_set = true;
        driver.m_uploadFileMode.m_value = strtol($1.c_str(), NULL, 8);
      }
    | CONFIG_UPLOAD_DIR
      {
        driver.m_uploadDirectory.m_set = true;
        driver.m_uploadDirectory.m_value = $1;
      }
    | CONFIG_UPDLOAD_SAVE_TMP_FILES CONFIG_VALUE_ON
      {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
    | CONFIG_UPDLOAD_SAVE_TMP_FILES CONFIG_VALUE_OFF
      {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
    ;

actions:
    QUOTATION_MARK actions_may_quoted QUOTATION_MARK
      {
        $$ = std::move($2);
      }
    | actions_may_quoted
      {
        $$ = std::move($1);
      }
    ;

actions_may_quoted:
    actions_may_quoted COMMA act
      {
        ACTION_INIT($3, @0)
        $1->push_back(std::move($3));
        $$ = std::move($1);
      }
    | act
      {
        std::unique_ptr<std::vector<std::unique_ptr<actions::Action>>> b(new std::vector<std::unique_ptr<actions::Action>>());
        ACTION_INIT($1, @0)
        b->push_back(std::move($1));
        $$ = std::move(b);
      }
    ;

op:
    op_before_init
      {
        $$ = std::move($1);
        std::string error;
        if ($$->init(*@1.end.filename, &error) == false) {
            driver.error(@0, error);
            YYERROR;
        }
      }
    | NOT op_before_init
      {
        $$ = std::move($2);
        $$->m_negation = true;
        std::string error;
        if ($$->init(*@1.end.filename, &error) == false) {
            driver.error(@0, error);
            YYERROR;
        }
      }
    | run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Rx(std::move($1)));
        std::string error;
        if ($$->init(*@1.end.filename, &error) == false) {
            driver.error(@0, error);
            YYERROR;
        }
      }
    | NOT run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Rx(std::move($2)));
        $$->m_negation = true;
        std::string error;
        if ($$->init(*@1.end.filename, &error) == false) {
            driver.error(@0, error);
            YYERROR;
        }
      }
    ;

op_before_init:
    OPERATOR_UNCONDITIONAL_MATCH
      {
        OPERATOR_CONTAINER($$, new operators::UnconditionalMatch());
      }
    | OPERATOR_DETECT_SQLI
      {
        OPERATOR_CONTAINER($$, new operators::DetectSQLi());
      }
    | OPERATOR_DETECT_XSS
      {
        OPERATOR_CONTAINER($$, new operators::DetectXSS());
      }
    | OPERATOR_VALIDATE_URL_ENCODING
      {
        OPERATOR_CONTAINER($$, new operators::ValidateUrlEncoding());
      }
    | OPERATOR_VALIDATE_UTF8_ENCODING
      {
        OPERATOR_CONTAINER($$, new operators::ValidateUtf8Encoding());
      }
    | OPERATOR_INSPECT_FILE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::InspectFile(std::move($2)));
      }
    | OPERATOR_FUZZY_HASH run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::FuzzyHash(std::move($2)));
      }
    | OPERATOR_VALIDATE_BYTE_RANGE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::ValidateByteRange(std::move($2)));
      }
    | OPERATOR_VALIDATE_DTD run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::ValidateDTD(std::move($2)));
      }
    | OPERATOR_VALIDATE_HASH run_time_string
      {
        /* $$ = new operators::ValidateHash($1); */
        OPERATOR_NOT_SUPPORTED("ValidateHash", @0);
      }
    | OPERATOR_VALIDATE_SCHEMA run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::ValidateSchema(std::move($2)));
      }
    | OPERATOR_VERIFY_CC run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::VerifyCC(std::move($2)));
      }
    | OPERATOR_VERIFY_CPF run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::VerifyCPF(std::move($2)));
      }
    | OPERATOR_VERIFY_SSN run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::VerifySSN(std::move($2)));
      }
    | OPERATOR_VERIFY_SVNR run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::VerifySVNR(std::move($2)));
      }
    | OPERATOR_GSB_LOOKUP run_time_string
      {
        /* $$ = new operators::GsbLookup($1); */
        OPERATOR_NOT_SUPPORTED("GsbLookup", @0);
      }
    | OPERATOR_RSUB run_time_string
      {
        /* $$ = new operators::Rsub($1); */
        OPERATOR_NOT_SUPPORTED("Rsub", @0);
      }
    | OPERATOR_WITHIN run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Within(std::move($2)));
      }
    | OPERATOR_CONTAINS_WORD run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::ContainsWord(std::move($2)));
      }
    | OPERATOR_CONTAINS run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Contains(std::move($2)));
      }
    | OPERATOR_ENDS_WITH run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::EndsWith(std::move($2)));
      }
    | OPERATOR_EQ run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Eq(std::move($2)));
      }
    | OPERATOR_GE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Ge(std::move($2)));
      }
    | OPERATOR_GT run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Gt(std::move($2)));
      }
    | OPERATOR_IP_MATCH_FROM_FILE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::IpMatchF(std::move($2)));
      }
    | OPERATOR_IP_MATCH run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::IpMatch(std::move($2)));
      }
    | OPERATOR_LE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Le(std::move($2)));
      }
    | OPERATOR_LT run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Lt(std::move($2)));
      }
    | OPERATOR_PM_FROM_FILE run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::PmFromFile(std::move($2)));
      }
    | OPERATOR_PM run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Pm(std::move($2)));
      }
    | OPERATOR_RBL run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Rbl(std::move($2)));
      }
    | OPERATOR_RX run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::Rx(std::move($2)));
      }
    | OPERATOR_RX_GLOBAL run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::RxGlobal(std::move($2)));
      }
    | OPERATOR_STR_EQ run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::StrEq(std::move($2)));
      }
    | OPERATOR_STR_MATCH run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::StrMatch(std::move($2)));
      }
    | OPERATOR_BEGINS_WITH run_time_string
      {
        OPERATOR_CONTAINER($$, new operators::BeginsWith(std::move($2)));
      }
    | OPERATOR_GEOLOOKUP
      {
#if defined(WITH_GEOIP) or defined(WITH_MAXMIND)
        OPERATOR_CONTAINER($$, new operators::GeoLookup());
#else
        std::stringstream ss;
            ss << "This version of ModSecurity was not compiled with GeoIP or MaxMind support.";
            driver.error(@0, ss.str());
            YYERROR;
#endif  // WITH_GEOIP
      }
    ;

expression:
    audit_log
    | DIRECTIVE variables op actions
      {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *$4.get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        variables::Variables *v = new variables::Variables();
        for (auto &i : *$2.get()) {
            v->push_back(i.release());
        }

        Operator *op = $3.release();
        std::unique_ptr<RuleWithOperator> rule(new RuleWithOperator(
            /* op */ op,
            /* variables */ v,
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*@1.end.filename)),
            /* line number */ @1.end.line
            ));

        if (driver.addSecRule(std::move(rule)) == false) {
            YYERROR;
        }
      }
    | DIRECTIVE variables op
      {
        variables::Variables *v = new variables::Variables();
        for (auto &i : *$2.get()) {
            v->push_back(i.release());
        }

        std::unique_ptr<RuleWithOperator> rule(new RuleWithOperator(
            /* op */ $3.release(),
            /* variables */ v,
            /* actions */ NULL,
            /* transformations */ NULL,
            /* file name */ std::unique_ptr<std::string>(new std::string(*@1.end.filename)),
            /* line number */ @1.end.line
            ));
        if (driver.addSecRule(std::move(rule)) == false) {
            YYERROR;
        }
      }
    | CONFIG_DIR_SEC_ACTION actions
      {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *$2.get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        std::unique_ptr<RuleUnconditional> rule(new RuleUnconditional(
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*@1.end.filename)),
            /* line number */ @1.end.line
            ));
        driver.addSecAction(std::move(rule));
      }
    | DIRECTIVE_SECRULESCRIPT actions
      {
        std::string err;
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *$2.get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        std::unique_ptr<RuleScript> r(new RuleScript(
            /* path to script */ $1,
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*@1.end.filename)),
            /* line number */ @1.end.line
            ));

        if (r->init(&err) == false) {
            driver.error(@0, "Failed to load script: " + err);
            YYERROR;
        }
        if (driver.addSecRuleScript(std::move(r)) == false) {
            YYERROR;
        }
      }
    | CONFIG_DIR_SEC_DEFAULT_ACTION actions
      {
        bool hasDisruptive = false;
        std::vector<actions::Action *> *actions = new std::vector<actions::Action *>();
        for (auto &i : *$2.get()) {
            actions->push_back(i.release());
        }
        std::vector<actions::Action *> checkedActions;
        int definedPhase = -1;
        int secRuleDefinedPhase = -1;
        for (actions::Action *a : *actions) {
            actions::Phase *phase = dynamic_cast<actions::Phase *>(a);
            if (a->isDisruptive() == true && dynamic_cast<actions::Block *>(a) == NULL) {
                hasDisruptive = true;
            }
            if (phase != NULL) {
                definedPhase = phase->m_phase;
                secRuleDefinedPhase = phase->m_secRulesPhase;
                delete phase;
            } else if (a->action_kind == actions::Action::RunTimeOnlyIfMatchKind ||
                a->action_kind == actions::Action::RunTimeBeforeMatchAttemptKind) {
                                actions::transformations::None *none = dynamic_cast<actions::transformations::None *>(a);
                if (none != NULL) {
                    driver.error(@0, "The transformation none is not suitable to be part of the SecDefaultActions");
                    YYERROR;
                }
                checkedActions.push_back(a);
            } else {
                driver.error(@0, "The action '" + *a->m_name.get() + "' is not suitable to be part of the SecDefaultActions");
                YYERROR;
            }
        }
        if (definedPhase == -1) {
            definedPhase = modsecurity::Phases::RequestHeadersPhase;
        }

        if (hasDisruptive == false) {
            driver.error(@0, "SecDefaultAction must specify a disruptive action.");
            YYERROR;
        }

        if (!driver.m_defaultActions[definedPhase].empty()) {
            std::stringstream ss;
            ss << "SecDefaultActions can only be placed once per phase and configuration context. Phase ";
            ss << secRuleDefinedPhase;
            ss << " was informed already.";
            driver.error(@0, ss.str());
            YYERROR;
        }

        for (actions::Action *a : checkedActions) {
            driver.m_defaultActions[definedPhase].push_back(
                std::unique_ptr<actions::Action>(a));
        }

        delete actions;
      }
    | CONFIG_DIR_SEC_MARKER
      {
        driver.addSecMarker(modsecurity::utils::string::removeBracketsIfNeeded($1),
            /* file name */ std::unique_ptr<std::string>(new std::string(*@1.end.filename)),
            /* line number */ @1.end.line
        );
      }
    | CONFIG_DIR_RULE_ENG CONFIG_VALUE_OFF
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::DisabledRuleEngine;
      }
    | CONFIG_DIR_RULE_ENG CONFIG_VALUE_ON
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::EnabledRuleEngine;
      }
    | CONFIG_DIR_RULE_ENG CONFIG_VALUE_DETC
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::DetectionOnlyRuleEngine;
      }
    | CONFIG_DIR_REQ_BODY CONFIG_VALUE_ON
      {
        driver.m_secRequestBodyAccess = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
    | CONFIG_DIR_REQ_BODY CONFIG_VALUE_OFF
      {
        driver.m_secRequestBodyAccess = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
    | CONFIG_DIR_RES_BODY CONFIG_VALUE_ON
      {
        driver.m_secResponseBodyAccess = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
    | CONFIG_DIR_RES_BODY CONFIG_VALUE_OFF
      {
        driver.m_secResponseBodyAccess = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
    | CONFIG_SEC_ARGUMENT_SEPARATOR
      {
        if ($1.length() != 1) {
          driver.error(@0, "Argument separator should be set to a single character.");
          YYERROR;
        }
        driver.m_secArgumentSeparator.m_value = $1;
        driver.m_secArgumentSeparator.m_set = true;
      }
    | CONFIG_COMPONENT_SIG
      {
        driver.m_components.push_back($1);
      }
    | CONFIG_CONN_ENGINE CONFIG_VALUE_ON
      {
        driver.error(@0, "SecConnEngine is not yet supported.");
        YYERROR;
      }
    | CONFIG_CONN_ENGINE CONFIG_VALUE_OFF
      {
      }
    | CONFIG_SEC_WEB_APP_ID
      {
        driver.m_secWebAppId.m_value = $1;
        driver.m_secWebAppId.m_set = true;
      }
    | CONFIG_SEC_SERVER_SIG
      {
        driver.error(@0, "SecServerSignature is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_CACHE_TRANSFORMATIONS
      {
        driver.error(@0, "SecCacheTransformations is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_DISABLE_BACKEND_COMPRESS CONFIG_VALUE_ON
      {
        driver.error(@0, "SecDisableBackendCompression is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_DISABLE_BACKEND_COMPRESS CONFIG_VALUE_OFF
      {
      }
    | CONFIG_CONTENT_INJECTION CONFIG_VALUE_ON
      {
        driver.error(@0, "SecContentInjection is not yet supported.");
        YYERROR;
      }
    | CONFIG_CONTENT_INJECTION CONFIG_VALUE_OFF
      {
      }
    | CONFIG_SEC_CHROOT_DIR
      {
        driver.error(@0, "SecChrootDir is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_HASH_ENGINE CONFIG_VALUE_ON
      {
        driver.error(@0, "SecHashEngine is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_HASH_ENGINE CONFIG_VALUE_OFF
      {
      }
    | CONFIG_SEC_HASH_KEY
      {
        driver.error(@0, "SecHashKey is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_HASH_PARAM
      {
        driver.error(@0, "SecHashParam is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_HASH_METHOD_RX
      {
        driver.error(@0, "SecHashMethodRx is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_HASH_METHOD_PM
      {
        driver.error(@0, "SecHashMethodPm is not yet supported.");
        YYERROR;
      }
    | CONFIG_DIR_GSB_DB
      {
        driver.error(@0, "SecGsbLookupDb is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_GUARDIAN_LOG
      {
        driver.error(@0, "SecGuardianLog is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_INTERCEPT_ON_ERROR CONFIG_VALUE_ON
      {
        driver.error(@0, "SecInterceptOnError is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_INTERCEPT_ON_ERROR CONFIG_VALUE_OFF
      {
      }
    | CONFIG_SEC_CONN_R_STATE_LIMIT
      {
        driver.error(@0, "SecConnReadStateLimit is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_CONN_W_STATE_LIMIT
      {
        driver.error(@0, "SecConnWriteStateLimit is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_SENSOR_ID
      {
        driver.error(@0, "SecSensorId is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_RULE_INHERITANCE CONFIG_VALUE_ON
      {
        driver.error(@0, "SecRuleInheritance is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_RULE_INHERITANCE CONFIG_VALUE_OFF
      {
      }
    | CONFIG_SEC_RULE_PERF_TIME
      {
        driver.error(@0, "SecRulePerfTime is not yet supported.");
        YYERROR;
      }
    | CONFIG_SEC_STREAM_IN_BODY_INSPECTION
      {
        driver.error(@0, "SecStreamInBodyInspection is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_STREAM_OUT_BODY_INSPECTION
      {
        driver.error(@0, "SecStreamOutBodyInspection is not supported.");
        YYERROR;
      }
    | CONFIG_SEC_RULE_REMOVE_BY_ID
      {
        std::string error;
        if (driver.m_exceptions.load($1, &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveById: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_REMOVE_BY_TAG
      {
        std::string error;
        if (driver.m_exceptions.loadRemoveRuleByTag($1, &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveByTag: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_REMOVE_BY_MSG
      {
        std::string error;
        if (driver.m_exceptions.loadRemoveRuleByMsg($1, &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveByMsg: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG variables_pre_process
      {
        std::string error;
        if (driver.m_exceptions.loadUpdateTargetByTag($1, std::move($2), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetByTag: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG variables_pre_process
      {
        std::string error;
        if (driver.m_exceptions.loadUpdateTargetByMsg($1, std::move($2), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetByMsg: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID variables_pre_process
      {
        std::string error;
        double ruleId;
        try {
            ruleId = std::stod($1);
        } catch (...) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetById: failed to load:";
            ss << "The input \"" + $1 + "\" does not ";
            ss << "seems to be a valid rule id.";
            ss << ". ";
            driver.error(@0, ss.str());
            YYERROR;
        }

        if (driver.m_exceptions.loadUpdateTargetById(ruleId, std::move($2), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetById: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID actions
      {
        std::string error;
        double ruleId;
        try {
            ruleId = std::stod($1);
        } catch (...) {
            std::stringstream ss;
            ss << "SecRuleUpdateActionById: failed to load:";
            ss << "The input \"" + $1 + "\" does not ";
            ss << "seems to be a valid rule id.";
            ss << ". ";
            driver.error(@0, ss.str());
            YYERROR;
        }


        if (driver.m_exceptions.loadUpdateActionById(ruleId, std::move($2), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateActionById: failed to load:";
            ss << $1;
            ss << ". ";
            ss << error;
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    /* Debug log: start */
    | CONFIG_DIR_DEBUG_LVL
      {
        if (driver.m_debugLog != NULL) {
          driver.m_debugLog->setDebugLogLevel(atoi($1.c_str()));
        } else {
            std::stringstream ss;
            ss << "Internal error, there is no DebugLog ";
            ss << "object associated with the driver class";
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    | CONFIG_DIR_DEBUG_LOG
      {
        if (driver.m_debugLog != NULL) {
            std::string error;
            driver.m_debugLog->setDebugLogFile($1, &error);
            if (error.size() > 0) {
                std::stringstream ss;
                ss << "Failed to start DebugLog: " << error;
                driver.error(@0, ss.str());
                YYERROR;
            }
        } else {
            std::stringstream ss;
            ss << "Internal error, there is no DebugLog ";
            ss << "object associated with the driver class";
            driver.error(@0, ss.str());
            YYERROR;
        }
      }
    /* Debug log: end */
    | CONFIG_DIR_GEO_DB
      {
#if defined(WITH_GEOIP) or defined(WITH_MAXMIND)
        std::string err;
        std::string file = modsecurity::utils::find_resource($1,
            *@1.end.filename, &err);
        if (file.empty()) {
            std::stringstream ss;
            ss << "Failed to load locate the GeoDB file from: " << $1 << " ";
            ss << err;
            driver.error(@0, ss.str());
            YYERROR;
        }
        if (Utils::GeoLookup::getInstance().setDataBase(file, &err) == false) {
            std::stringstream ss;
            ss << "Failed to load the GeoDB from: ";
            ss << file << ". " << err;
            driver.error(@0, ss.str());
            YYERROR;
        }
#else
        std::stringstream ss;
        ss << "This version of ModSecurity was not compiled with GeoIP or MaxMind support.";
        driver.error(@0, ss.str());
        YYERROR;
#endif  // WITH_GEOIP
      }
    | CONFIG_DIR_ARGS_LIMIT
      {
        driver.m_argumentsLimit.m_set = true;
        driver.m_argumentsLimit.m_value = atoi($1.c_str());
      }
    | CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT
      {
        driver.m_requestBodyJsonDepthLimit.m_set = true;
        driver.m_requestBodyJsonDepthLimit.m_value = atoi($1.c_str());
      }
    /* Body limits */
    | CONFIG_DIR_REQ_BODY_LIMIT
      {
        driver.m_requestBodyLimit.m_set = true;
        driver.m_requestBodyLimit.m_value = atoi($1.c_str());
      }
    | CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT
      {
        driver.m_requestBodyNoFilesLimit.m_set = true;
        driver.m_requestBodyNoFilesLimit.m_value = atoi($1.c_str());
      }
    | CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT
      {
        std::stringstream ss;
        ss << "As of ModSecurity version 3.0, SecRequestBodyInMemoryLimit is no longer ";
        ss << "supported. Instead, you can use your web server configurations to control ";
        ss << "those values. ModSecurity will follow the web server decision.";
        driver.error(@0, ss.str());
        YYERROR;
      }
    | CONFIG_DIR_RES_BODY_LIMIT
      {
        driver.m_responseBodyLimit.m_set = true;
        driver.m_responseBodyLimit.m_value = atoi($1.c_str());
      }
    | CONFIG_DIR_REQ_BODY_LIMIT_ACTION CONFIG_VALUE_PROCESS_PARTIAL
      {
        driver.m_requestBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
    | CONFIG_DIR_REQ_BODY_LIMIT_ACTION CONFIG_VALUE_REJECT
      {
        driver.m_requestBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::RejectBodyLimitAction;
      }
    | CONFIG_DIR_RES_BODY_LIMIT_ACTION CONFIG_VALUE_PROCESS_PARTIAL
      {
        driver.m_responseBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
    | CONFIG_DIR_RES_BODY_LIMIT_ACTION CONFIG_VALUE_REJECT
      {
        driver.m_responseBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::RejectBodyLimitAction;
      }
    | CONFIG_SEC_REMOTE_RULES_FAIL_ACTION CONFIG_VALUE_ABORT
      {
        driver.m_remoteRulesActionOnFailed = RulesSet::OnFailedRemoteRulesAction::AbortOnFailedRemoteRulesAction;
      }
    | CONFIG_SEC_REMOTE_RULES_FAIL_ACTION CONFIG_VALUE_WARN
      {
        driver.m_remoteRulesActionOnFailed = RulesSet::OnFailedRemoteRulesAction::WarnOnFailedRemoteRulesAction;
      }
    | CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        driver.error(@0, "SecPcreMatchLimitRecursion is not currently supported. Default PCRE values are being used for now");
        YYERROR;
*/
    | CONFIG_DIR_PCRE_MATCH_LIMIT
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        driver.error(@0, "SecPcreMatchLimit is not currently supported. Default PCRE values are being used for now");
        YYERROR;
*/
    | CONGIG_DIR_RESPONSE_BODY_MP
      {
        std::istringstream buf($1);
        std::istream_iterator<std::string> beg(buf), end;
        std::set<std::string> tokens(beg, end);
        driver.m_responseBodyTypeToBeInspected.m_set = true;
        for (std::set<std::string>::iterator it=tokens.begin();
            it!=tokens.end(); ++it)
        {
            driver.m_responseBodyTypeToBeInspected.m_value.insert(*it);
        }
      }
    | CONGIG_DIR_RESPONSE_BODY_MP_CLEAR
      {
        driver.m_responseBodyTypeToBeInspected.m_set = true;
        driver.m_responseBodyTypeToBeInspected.m_clear = true;
        driver.m_responseBodyTypeToBeInspected.m_value.clear();
      }
    | CONFIG_XML_EXTERNAL_ENTITY CONFIG_VALUE_OFF
      {
        driver.m_secXMLExternalEntity = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
    | CONFIG_XML_EXTERNAL_ENTITY CONFIG_VALUE_ON
      {
        driver.m_secXMLExternalEntity = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
    | CONGIG_DIR_SEC_TMP_DIR
      {
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        std::stringstream ss;
        ss << "As of ModSecurity version 3.0, SecTmpDir is no longer supported.";
        ss << " Instead, you can use your web server configurations to control when";
        ss << "and where to swap. ModSecurity will follow the web server decision.";
        driver.error(@0, ss.str());
        YYERROR;
*/
      }
    | CONGIG_DIR_SEC_DATA_DIR
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        std::stringstream ss;
        ss << "SecDataDir is not currently supported.";
        ss << " Collections are kept in memory (in_memory-per_process) for now.";
        ss << " When using a backend such as LMDB, temp data path is currently defined by the backend.";
        driver.error(@0, ss.str());
        YYERROR;
*/
    | CONGIG_DIR_SEC_ARG_SEP
    | CONGIG_DIR_SEC_COOKIE_FORMAT
      {
        if (atoi($1.c_str()) == 1) {
          driver.error(@0, "SecCookieFormat 1 is not yet supported.");
          YYERROR;
        }
      }
    | CONFIG_SEC_COOKIEV0_SEPARATOR
      {
        driver.error(@0, "SecCookieV0Separator is not yet supported.");
        YYERROR;
      }
    | CONGIG_DIR_SEC_STATUS_ENGINE
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        driver.error(@0, "SecStatusEngine is not yet supported.");
        YYERROR;
*/
    | CONFIG_DIR_UNICODE_MAP_FILE
      {
        std::string error;
        std::vector<std::string> param;
        double num = 0;
        std::string f;
        std::string file;
        std::string err;
        param = utils::string::ssplit($1, ' ');
        if (param.size() <= 1) {
            std::stringstream ss;
            ss << "Failed to process unicode map, missing ";
            ss << "parameter: " << $1 << " ";
            driver.error(@0, ss.str());
            YYERROR;
        }

        try {
            num = std::stod(param.back());
        } catch (...) {
            std::stringstream ss;
            ss << "Failed to process unicode map, last parameter is ";
            ss << "expected to be a number: " << param.back() << " ";
            driver.error(@0, ss.str());
            YYERROR;
        }
        param.pop_back();

        while (param.size() > 0) {
            if (f.empty()) {
                f = param.back();
            } else {
                f = param.back() + " " + f;
            }
            param.pop_back();
        }

        file = modsecurity::utils::find_resource(f, *@1.end.filename, &err);
        if (file.empty()) {
            std::stringstream ss;
            ss << "Failed to locate the unicode map file from: " << f << " ";
            ss << err;
            driver.error(@0, ss.str());
            YYERROR;
        }

        ConfigUnicodeMap::loadConfig(file, num, &driver, &error);

        if (!error.empty()) {
            driver.error(@0, error);
            YYERROR;
        }

      }
    | CONFIG_SEC_COLLECTION_TIMEOUT
      {
/* Parser error disabled to avoid breaking default CRS installations with crs-setup.conf-recommended
        driver.error(@0, "SecCollectionTimeout is not yet supported.");
        YYERROR;
*/
      }
    | CONFIG_SEC_HTTP_BLKEY
      {
        driver.m_httpblKey.m_set = true;
        driver.m_httpblKey.m_value = $1;
      }
    ;

variables:
    variables_pre_process
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable> > > originalList = std::move($1);
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> newList(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> newNewList(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> exclusionVars(new std::vector<std::unique_ptr<Variable>>());
        while (!originalList->empty()) {
            std::unique_ptr<Variable> var = std::move(originalList->back());
            originalList->pop_back();
            if (dynamic_cast<VariableModificatorExclusion*>(var.get())) {
                exclusionVars->push_back(std::move(var));
            } else {
                newList->push_back(std::move(var));
            }
        }

        while (!newList->empty()) {
            bool doNotAdd = false;
            std::unique_ptr<Variable> var = std::move(newList->back());
            newList->pop_back();
            for (auto &i : *exclusionVars) {
                if (*var == *i) {
                    doNotAdd = true;
                }
                if (i->belongsToCollection(var.get())) {
                    var->addsKeyExclusion(i.get());
                }
            }
            if (!doNotAdd) {
                newNewList->push_back(std::move(var));
            }
        }
        $$ = std::move(newNewList);
      }
    ;

variables_pre_process:
    variables_may_be_quoted
      {
        $$ = std::move($1);
      }
    | QUOTATION_MARK variables_may_be_quoted QUOTATION_MARK
      {
        $$ = std::move($2);
      }
    ;

variables_may_be_quoted:
    variables_may_be_quoted PIPE var
      {
        $1->push_back(std::move($3));
        $$ = std::move($1);
      }
    | variables_may_be_quoted PIPE VAR_EXCLUSION var
      {
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move($4)));
        $1->push_back(std::move(c));
        $$ = std::move($1);
      }
    | variables_may_be_quoted PIPE VAR_COUNT var
      {
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move($4)));
        $1->push_back(std::move(c));
        $$ = std::move($1);
      }
    | var
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        b->push_back(std::move($1));
        $$ = std::move(b);
      }
    | VAR_EXCLUSION var
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move($2)));
        b->push_back(std::move(c));
        $$ = std::move(b);
      }
    | VAR_COUNT var
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move($2)));
        b->push_back(std::move(c));
        $$ = std::move(b);
      }
    ;

var:
    VARIABLE_ARGS DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Args_DictElement($2));
      }
    | VARIABLE_ARGS DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Args_DictElementRegexp($2));
      }
    | VARIABLE_ARGS
      {
        VARIABLE_CONTAINER($$, new variables::Args_NoDictElement());
      }
    | VARIABLE_ARGS_POST DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPost_DictElement($2));
      }
    | VARIABLE_ARGS_POST DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPost_DictElementRegexp($2));
      }
    | VARIABLE_ARGS_POST
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPost_NoDictElement());
      }
    | VARIABLE_ARGS_GET DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGet_DictElement($2));
      }
    | VARIABLE_ARGS_GET DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGet_DictElementRegexp($2));
      }
    | VARIABLE_ARGS_GET
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGet_NoDictElement());
      }
    | VARIABLE_FILES_SIZES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::FilesSizes_DictElement($2));
      }
    | VARIABLE_FILES_SIZES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::FilesSizes_DictElementRegexp($2));
      }
    | VARIABLE_FILES_SIZES
      {
        VARIABLE_CONTAINER($$, new variables::FilesSizes_NoDictElement());
      }
    | VARIABLE_FILES_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::FilesNames_DictElement($2));
      }
    | VARIABLE_FILES_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::FilesNames_DictElementRegexp($2));
      }
    | VARIABLE_FILES_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::FilesNames_NoDictElement());
      }
    | VARIABLE_FILES_TMP_CONTENT DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpContent_DictElement($2));
      }
    | VARIABLE_FILES_TMP_CONTENT DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpContent_DictElementRegexp($2));
      }
    | VARIABLE_FILES_TMP_CONTENT
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpContent_NoDictElement());
      }
    | VARIABLE_MULTIPART_FILENAME DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartFileName_DictElement($2));
      }
    | VARIABLE_MULTIPART_FILENAME DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartFileName_DictElementRegexp($2));
      }
    | VARIABLE_MULTIPART_FILENAME
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartFileName_NoDictElement());
      }
    | VARIABLE_MULTIPART_NAME DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartName_DictElement($2));
      }
    | VARIABLE_MULTIPART_NAME DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartName_DictElementRegexp($2));
      }
    | VARIABLE_MULTIPART_NAME
      {
        VARIABLE_CONTAINER($$, new variables::MultiPartName_NoDictElement());
      }
    | VARIABLE_MATCHED_VARS_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVarsNames_DictElement($2));
      }
    | VARIABLE_MATCHED_VARS_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVarsNames_DictElementRegexp($2));
      }
    | VARIABLE_MATCHED_VARS_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVarsNames_NoDictElement());
      }
    | VARIABLE_MATCHED_VARS DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVars_DictElement($2));
      }
    | VARIABLE_MATCHED_VARS DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVars_DictElementRegexp($2));
      }
    | VARIABLE_MATCHED_VARS
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVars_NoDictElement());
      }
    | VARIABLE_FILES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Files_DictElement($2));
      }
    | VARIABLE_FILES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Files_DictElementRegexp($2));
      }
    | VARIABLE_FILES
      {
        VARIABLE_CONTAINER($$, new variables::Files_NoDictElement());
      }
    | VARIABLE_REQUEST_COOKIES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookies_DictElement($2));
      }
    | VARIABLE_REQUEST_COOKIES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookies_DictElementRegexp($2));
      }
    | VARIABLE_REQUEST_COOKIES
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookies_NoDictElement());
      }
    | VARIABLE_REQUEST_HEADERS DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeaders_DictElement($2));
      }
    | VARIABLE_REQUEST_HEADERS DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeaders_DictElementRegexp($2));
      }
    | VARIABLE_REQUEST_HEADERS
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeaders_NoDictElement());
      }
    | VARIABLE_RESPONSE_HEADERS DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeaders_DictElement($2));
      }
    | VARIABLE_RESPONSE_HEADERS DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeaders_DictElementRegexp($2));
      }
    | VARIABLE_RESPONSE_HEADERS
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeaders_NoDictElement());
      }
    | VARIABLE_GEO DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Geo_DictElement($2));
      }
    | VARIABLE_GEO DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Geo_DictElementRegexp($2));
      }
    | VARIABLE_GEO
      {
        VARIABLE_CONTAINER($$, new variables::Geo_NoDictElement());
      }
    | VARIABLE_REQUEST_COOKIES_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookiesNames_DictElement($2));
      }
    | VARIABLE_REQUEST_COOKIES_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookiesNames_DictElementRegexp($2));
      }
    | VARIABLE_REQUEST_COOKIES_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::RequestCookiesNames_NoDictElement());
      }
    | VARIABLE_MULTIPART_PART_HEADERS DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::MultipartPartHeaders_DictElement($2));
      }
    | VARIABLE_MULTIPART_PART_HEADERS DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::MultipartPartHeaders_DictElementRegexp($2));
      }
    | VARIABLE_MULTIPART_PART_HEADERS
      {
        VARIABLE_CONTAINER($$, new variables::MultipartPartHeaders_NoDictElement());
      }
    | VARIABLE_RULE DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Rule_DictElement($2));
      }
    | VARIABLE_RULE DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Rule_DictElementRegexp($2));
      }
    | VARIABLE_RULE
      {
        VARIABLE_CONTAINER($$, new variables::Rule_NoDictElement());
      }
    | RUN_TIME_VAR_ENV DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Env("ENV:" + $2));
      }
    | RUN_TIME_VAR_ENV DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Env("ENV:" + $2));
      }
    | RUN_TIME_VAR_ENV
      {
        VARIABLE_CONTAINER($$, new variables::Env("ENV"));
      }
    | RUN_TIME_VAR_XML DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::XML("XML:" + $2));
      }
    | RUN_TIME_VAR_XML DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::XML("XML:" + $2));
      }
    | RUN_TIME_VAR_XML
      {
        VARIABLE_CONTAINER($$, new variables::XML_NoDictElement());
      }
    | VARIABLE_FILES_TMP_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpNames_DictElement($2));
      }
    | VARIABLE_FILES_TMP_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpNames_DictElementRegexp($2));
      }
    | VARIABLE_FILES_TMP_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::FilesTmpNames_NoDictElement());
      }
    | VARIABLE_RESOURCE run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::Resource_DynamicElement(std::move($2)));
      }
    | VARIABLE_RESOURCE DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Resource_DictElement($2));
      }
    | VARIABLE_RESOURCE DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Resource_DictElementRegexp($2));
      }
    | VARIABLE_RESOURCE
      {
        VARIABLE_CONTAINER($$, new variables::Resource_NoDictElement());
      }
    | VARIABLE_IP run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::Ip_DynamicElement(std::move($2)));
      }
    | VARIABLE_IP DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Ip_DictElement($2));
      }
    | VARIABLE_IP DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Ip_DictElementRegexp($2));
      }
    | VARIABLE_IP
      {
        VARIABLE_CONTAINER($$, new variables::Ip_NoDictElement());
      }
    | VARIABLE_GLOBAL run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::Global_DynamicElement(std::move($2)));
      }
    | VARIABLE_GLOBAL DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Global_DictElement($2));
      }
    | VARIABLE_GLOBAL DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Global_DictElementRegexp($2));
      }
    | VARIABLE_GLOBAL
      {
        VARIABLE_CONTAINER($$, new variables::Global_NoDictElement());
      }
    | VARIABLE_USER run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::User_DynamicElement(std::move($2)));
      }
    | VARIABLE_USER DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::User_DictElement($2));
      }
    | VARIABLE_USER DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::User_DictElementRegexp($2));
      }
    | VARIABLE_USER
      {
        VARIABLE_CONTAINER($$, new variables::User_NoDictElement());
      }
    | VARIABLE_TX run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::Tx_DynamicElement(std::move($2)));
      }
    | VARIABLE_TX DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Tx_DictElement($2));
      }
    | VARIABLE_TX DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Tx_DictElementRegexp($2));
      }
    | VARIABLE_TX
      {
        VARIABLE_CONTAINER($$, new variables::Tx_NoDictElement());
      }
    | VARIABLE_SESSION run_time_string
      {
        VARIABLE_CONTAINER($$, new variables::Session_DynamicElement(std::move($2)));
      }
    | VARIABLE_SESSION DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::Session_DictElement($2));
      }
    | VARIABLE_SESSION DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::Session_DictElementRegexp($2));
      }
    | VARIABLE_SESSION
      {
        VARIABLE_CONTAINER($$, new variables::Session_NoDictElement());
      }
    | VARIABLE_ARGS_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ArgsNames_DictElement($2));
      }
    | VARIABLE_ARGS_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ArgsNames_DictElementRegexp($2));
      }
    | VARIABLE_ARGS_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::ArgsNames_NoDictElement());
      }
    | VARIABLE_ARGS_GET_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGetNames_DictElement($2));
      }
    | VARIABLE_ARGS_GET_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGetNames_DictElementRegexp($2));
      }
    | VARIABLE_ARGS_GET_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::ArgsGetNames_NoDictElement());
      }

    | VARIABLE_ARGS_POST_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPostNames_DictElement($2));
      }
    | VARIABLE_ARGS_POST_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPostNames_DictElementRegexp($2));
      }
    | VARIABLE_ARGS_POST_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::ArgsPostNames_NoDictElement());
      }

    | VARIABLE_REQUEST_HEADERS_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeadersNames_DictElement($2));
      }
    | VARIABLE_REQUEST_HEADERS_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeadersNames_DictElementRegexp($2));
      }
    | VARIABLE_REQUEST_HEADERS_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::RequestHeadersNames_NoDictElement());
      }

    | VARIABLE_RESPONSE_CONTENT_TYPE
      {
        VARIABLE_CONTAINER($$, new variables::ResponseContentType());
      }

    | VARIABLE_RESPONSE_HEADERS_NAMES DICT_ELEMENT
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeadersNames_DictElement($2));
      }
    | VARIABLE_RESPONSE_HEADERS_NAMES DICT_ELEMENT_REGEXP
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeadersNames_DictElementRegexp($2));
      }
    | VARIABLE_RESPONSE_HEADERS_NAMES
      {
        VARIABLE_CONTAINER($$, new variables::ResponseHeadersNames_NoDictElement());
      }
    | VARIABLE_ARGS_COMBINED_SIZE
      {
        VARIABLE_CONTAINER($$, new variables::ArgsCombinedSize());
      }
   | VARIABLE_AUTH_TYPE
      {
        VARIABLE_CONTAINER($$, new variables::AuthType());
      }
    | VARIABLE_FILES_COMBINED_SIZE
      {
        VARIABLE_CONTAINER($$, new variables::FilesCombinedSize());
      }
    | VARIABLE_FULL_REQUEST
      {
        VARIABLE_CONTAINER($$, new variables::FullRequest());
      }
    | VARIABLE_FULL_REQUEST_LENGTH
      {
        VARIABLE_CONTAINER($$, new variables::FullRequestLength());
      }
    | VARIABLE_INBOUND_DATA_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::InboundDataError());
      }
    | VARIABLE_MATCHED_VAR
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVar());
      }
    | VARIABLE_MATCHED_VAR_NAME
      {
        VARIABLE_CONTAINER($$, new variables::MatchedVarName());
      }
    | VARIABLE_MULTIPART_BOUNDARY_QUOTED
      {
        VARIABLE_CONTAINER($$, new variables::MultipartBoundaryQuoted());
      }
    | VARIABLE_MULTIPART_BOUNDARY_WHITESPACE
      {
        VARIABLE_CONTAINER($$, new variables::MultipartBoundaryWhiteSpace());
      }
    | VARIABLE_MULTIPART_CRLF_LF_LINES
      {
        VARIABLE_CONTAINER($$, new variables::MultipartCrlfLFLines());
      }
    | VARIABLE_MULTIPART_DATA_AFTER
      {
        VARIABLE_CONTAINER($$, new variables::MultipartDateAfter());
      }
    | VARIABLE_MULTIPART_DATA_BEFORE
      {
        VARIABLE_CONTAINER($$, new variables::MultipartDateBefore());
      }
    | VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED
      {
        VARIABLE_CONTAINER($$, new variables::MultipartFileLimitExceeded());
      }
    | VARIABLE_MULTIPART_HEADER_FOLDING
      {
        VARIABLE_CONTAINER($$, new variables::MultipartHeaderFolding());
      }
    | VARIABLE_MULTIPART_INVALID_HEADER_FOLDING
      {
        VARIABLE_CONTAINER($$, new variables::MultipartInvalidHeaderFolding());
      }
    | VARIABLE_MULTIPART_INVALID_PART
      {
        VARIABLE_CONTAINER($$, new variables::MultipartInvalidPart());
      }
    | VARIABLE_MULTIPART_INVALID_QUOTING
      {
        VARIABLE_CONTAINER($$, new variables::MultipartInvalidQuoting());
      }
    | VARIABLE_MULTIPART_LF_LINE
      {
        VARIABLE_CONTAINER($$, new variables::MultipartLFLine());
      }
    | VARIABLE_MULTIPART_MISSING_SEMICOLON
      {
        VARIABLE_CONTAINER($$, new variables::MultipartMissingSemicolon());
      }
    | VARIABLE_MULTIPART_SEMICOLON_MISSING
      {
        VARIABLE_CONTAINER($$, new variables::MultipartMissingSemicolon());
      }
    | VARIABLE_MULTIPART_STRICT_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::MultipartStrictError());
      }
    | VARIABLE_MULTIPART_UNMATCHED_BOUNDARY
      {
        VARIABLE_CONTAINER($$, new variables::MultipartUnmatchedBoundary());
      }
    | VARIABLE_OUTBOUND_DATA_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::OutboundDataError());
      }
    | VARIABLE_PATH_INFO
      {
        VARIABLE_CONTAINER($$, new variables::PathInfo());
      }
    | VARIABLE_QUERY_STRING
      {
        VARIABLE_CONTAINER($$, new variables::QueryString());
      }
    | VARIABLE_REMOTE_ADDR
      {
        VARIABLE_CONTAINER($$, new variables::RemoteAddr());
      }
    | VARIABLE_REMOTE_HOST
      {
        VARIABLE_CONTAINER($$, new variables::RemoteHost());
      }
    | VARIABLE_REMOTE_PORT
      {
        VARIABLE_CONTAINER($$, new variables::RemotePort());
      }
    | VARIABLE_REQBODY_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::ReqbodyError());
      }
    | VARIABLE_REQBODY_ERROR_MSG
      {
        VARIABLE_CONTAINER($$, new variables::ReqbodyErrorMsg());
      }
    | VARIABLE_REQBODY_PROCESSOR
      {
        VARIABLE_CONTAINER($$, new variables::ReqbodyProcessor());
      }
    | VARIABLE_REQBODY_PROCESSOR_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::ReqbodyProcessorError());
      }
    | VARIABLE_REQBODY_PROCESSOR_ERROR_MSG
      {
        VARIABLE_CONTAINER($$, new variables::ReqbodyProcessorErrorMsg());
      }
    | VARIABLE_REQUEST_BASENAME
      {
        VARIABLE_CONTAINER($$, new variables::RequestBasename());
      }
    | VARIABLE_REQUEST_BODY
      {
        VARIABLE_CONTAINER($$, new variables::RequestBody());
      }
    | VARIABLE_REQUEST_BODY_LENGTH
      {
        VARIABLE_CONTAINER($$, new variables::RequestBodyLength());
      }
    | VARIABLE_REQUEST_FILE_NAME
      {
        VARIABLE_CONTAINER($$, new variables::RequestFilename());
      }
    | VARIABLE_REQUEST_LINE
      {
        VARIABLE_CONTAINER($$, new variables::RequestLine());
      }
    | VARIABLE_REQUEST_METHOD
      {
        VARIABLE_CONTAINER($$, new variables::RequestMethod());
      }
    | VARIABLE_REQUEST_PROTOCOL
      {
        VARIABLE_CONTAINER($$, new variables::RequestProtocol());
      }
    | VARIABLE_REQUEST_URI
      {
        VARIABLE_CONTAINER($$, new variables::RequestURI());
      }
    | VARIABLE_REQUEST_URI_RAW
      {
        VARIABLE_CONTAINER($$, new variables::RequestURIRaw());
      }
    | VARIABLE_RESPONSE_BODY
      {
        VARIABLE_CONTAINER($$, new variables::ResponseBody());
      }
    | VARIABLE_RESPONSE_CONTENT_LENGTH
      {
        VARIABLE_CONTAINER($$, new variables::ResponseContentLength());
      }
    | VARIABLE_RESPONSE_PROTOCOL
      {
        VARIABLE_CONTAINER($$, new variables::ResponseProtocol());
      }
    | VARIABLE_RESPONSE_STATUS
      {
        VARIABLE_CONTAINER($$, new variables::ResponseStatus());
      }
    | VARIABLE_SERVER_ADDR
      {
        VARIABLE_CONTAINER($$, new variables::ServerAddr());
      }
    | VARIABLE_SERVER_NAME
      {
        VARIABLE_CONTAINER($$, new variables::ServerName());
      }
    | VARIABLE_SERVER_PORT
      {
        VARIABLE_CONTAINER($$, new variables::ServerPort());
      }
    | VARIABLE_SESSION_ID
      {
        VARIABLE_CONTAINER($$, new variables::SessionID());
      }
    | VARIABLE_UNIQUE_ID
      {
        VARIABLE_CONTAINER($$, new variables::UniqueID());
      }
    | VARIABLE_URL_ENCODED_ERROR
      {
        VARIABLE_CONTAINER($$, new variables::UrlEncodedError());
      }
    | VARIABLE_USER_ID
      {
        VARIABLE_CONTAINER($$, new variables::UserID());
      }
    | VARIABLE_STATUS
      {
        VARIABLE_CONTAINER($$, new variables::Status());
      }
    | VARIABLE_STATUS_LINE
      {
        VARIABLE_CONTAINER($$, new variables::Status());
      }
    | VARIABLE_WEB_APP_ID
      {
        VARIABLE_CONTAINER($$, new variables::WebAppId());
      }
    | RUN_TIME_VAR_DUR
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Duration(name));
        $$ = std::move(c);
      }

    | RUN_TIME_VAR_BLD
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new ModsecBuild(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_HSV
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new HighestSeverity(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_REMOTE_USER
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new RemoteUser(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Time(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_DAY
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeDay(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_EPOCH
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeEpoch(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_HOUR
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeHour(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_MIN
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMin(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_MON
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMon(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_SEC
      {
        std::string name($1);
        char z = name.at(0);
            std::unique_ptr<Variable> c(new TimeSec(name));
            $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_WDAY
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeWDay(name));
        $$ = std::move(c);
      }
    | RUN_TIME_VAR_TIME_YEAR
      {
        std::string name($1);
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeYear(name));
        $$ = std::move(c);
      }
    ;

act:
    ACTION_ACCURACY
      {
        ACTION_CONTAINER($$, new actions::Accuracy($1));
      }
    | ACTION_ALLOW
      {
        ACTION_CONTAINER($$, new actions::disruptive::Allow($1));
      }
    | ACTION_APPEND
      {
        ACTION_NOT_SUPPORTED("Append", @0);
      }
    | ACTION_AUDIT_LOG
      {
        ACTION_CONTAINER($$, new actions::AuditLog($1));
      }
    | ACTION_BLOCK
      {
        ACTION_CONTAINER($$, new actions::Block($1));
      }
    | ACTION_CAPTURE
      {
        ACTION_CONTAINER($$, new actions::Capture($1));
      }
    | ACTION_CHAIN
      {
        ACTION_CONTAINER($$, new actions::Chain($1));
      }
    | ACTION_CTL_AUDIT_ENGINE CONFIG_VALUE_ON
      {
        ACTION_CONTAINER($$, new actions::ctl::AuditEngine("ctl:auditengine=on"));
        driver.m_auditLog->setCtlAuditEngineActive();
      }
    | ACTION_CTL_AUDIT_ENGINE CONFIG_VALUE_OFF
      {
        ACTION_CONTAINER($$, new actions::ctl::AuditEngine("ctl:auditengine=off"));
      }
    | ACTION_CTL_AUDIT_ENGINE CONFIG_VALUE_RELEVANT_ONLY
      {
        ACTION_CONTAINER($$, new actions::ctl::AuditEngine("ctl:auditengine=relevantonly"));
        driver.m_auditLog->setCtlAuditEngineActive();
      }
    | ACTION_CTL_AUDIT_LOG_PARTS
      {
        ACTION_CONTAINER($$, new actions::ctl::AuditLogParts($1));
      }
    | ACTION_CTL_BDY_JSON
      {
        ACTION_CONTAINER($$, new actions::ctl::RequestBodyProcessorJSON($1));
      }
    | ACTION_CTL_BDY_XML
      {
        ACTION_CONTAINER($$, new actions::ctl::RequestBodyProcessorXML($1));
      }
    | ACTION_CTL_BDY_URLENCODED
      {
        ACTION_CONTAINER($$, new actions::ctl::RequestBodyProcessorURLENCODED($1));
      }
    | ACTION_CTL_FORCE_REQ_BODY_VAR CONFIG_VALUE_ON
      {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER($$, new actions::Action($1));
      }
    | ACTION_CTL_FORCE_REQ_BODY_VAR CONFIG_VALUE_OFF
      {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER($$, new actions::Action($1));
      }
    | ACTION_CTL_REQUEST_BODY_ACCESS CONFIG_VALUE_ON
      {
        ACTION_CONTAINER($$, new actions::ctl::RequestBodyAccess($1 + "true"));
      }
    | ACTION_CTL_REQUEST_BODY_ACCESS CONFIG_VALUE_OFF
      {
        ACTION_CONTAINER($$, new actions::ctl::RequestBodyAccess($1 + "false"));
      }
    | ACTION_CTL_RULE_ENGINE CONFIG_VALUE_ON
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleEngine("ctl:RuleEngine=on"));
      }
    | ACTION_CTL_RULE_ENGINE CONFIG_VALUE_OFF
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleEngine("ctl:RuleEngine=off"));
      }
    | ACTION_CTL_RULE_ENGINE CONFIG_VALUE_DETC
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleEngine("ctl:RuleEngine=detectiononly"));
      }
    | ACTION_CTL_RULE_REMOVE_BY_ID
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleRemoveById($1));
      }
    | ACTION_CTL_RULE_REMOVE_BY_TAG
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleRemoveByTag($1));
      }
    | ACTION_CTL_RULE_REMOVE_TARGET_BY_ID
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleRemoveTargetById($1));
      }
    | ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG
      {
        ACTION_CONTAINER($$, new actions::ctl::RuleRemoveTargetByTag($1));
      }
    | ACTION_DENY
      {
        ACTION_CONTAINER($$, new actions::disruptive::Deny($1));
      }
    | ACTION_DEPRECATE_VAR
      {
        ACTION_NOT_SUPPORTED("DeprecateVar", @0);
      }
    | ACTION_DROP
      {
        ACTION_CONTAINER($$, new actions::disruptive::Drop($1));
      }
    | ACTION_EXEC
      {
        ACTION_CONTAINER($$, new actions::Exec($1));
      }
    | ACTION_EXPIRE_VAR
      {
        //ACTION_NOT_SUPPORTED("ExpireVar", @0);
        ACTION_CONTAINER($$, new actions::Action($1));
      }
    | ACTION_ID
      {
        ACTION_CONTAINER($$, new actions::RuleId($1));
      }
    | ACTION_INITCOL run_time_string
      {
        ACTION_CONTAINER($$, new actions::InitCol($1, std::move($2)));
      }
    | ACTION_LOG_DATA run_time_string
      {
        ACTION_CONTAINER($$, new actions::LogData(std::move($2)));
      }
    | ACTION_LOG
      {
        ACTION_CONTAINER($$, new actions::Log($1));
      }
    | ACTION_MATURITY
      {
        ACTION_CONTAINER($$, new actions::Maturity($1));
      }
    | ACTION_MSG run_time_string
      {
        ACTION_CONTAINER($$, new actions::Msg(std::move($2)));
      }
    | ACTION_MULTI_MATCH
      {
        ACTION_CONTAINER($$, new actions::MultiMatch($1));
      }
    | ACTION_NO_AUDIT_LOG
      {
        ACTION_CONTAINER($$, new actions::NoAuditLog($1));
      }
    | ACTION_NO_LOG
      {
        ACTION_CONTAINER($$, new actions::NoLog($1));
      }
    | ACTION_PASS
      {
        ACTION_CONTAINER($$, new actions::disruptive::Pass($1));
      }
    | ACTION_PAUSE
      {
        ACTION_NOT_SUPPORTED("Pause", @0);
      }
    | ACTION_PHASE
      {
        ACTION_CONTAINER($$, new actions::Phase($1));
      }
    | ACTION_PREPEND
      {
        ACTION_NOT_SUPPORTED("Prepend", @0);
      }
    | ACTION_PROXY
      {
        ACTION_NOT_SUPPORTED("Proxy", @0);
      }
    | ACTION_REDIRECT run_time_string
      {
        ACTION_CONTAINER($$, new actions::disruptive::Redirect(std::move($2)));
      }
    | ACTION_REV
      {
        ACTION_CONTAINER($$, new actions::Rev($1));
      }
    | ACTION_SANITISE_ARG
      {
        ACTION_NOT_SUPPORTED("SanitiseArg", @0);
      }
    | ACTION_SANITISE_MATCHED
      {
        ACTION_NOT_SUPPORTED("SanitiseMatched", @0);
      }
    | ACTION_SANITISE_MATCHED_BYTES
      {
        ACTION_NOT_SUPPORTED("SanitiseMatchedBytes", @0);
      }
    | ACTION_SANITISE_REQUEST_HEADER
      {
        ACTION_NOT_SUPPORTED("SanitiseRequestHeader", @0);
      }
    | ACTION_SANITISE_RESPONSE_HEADER
      {
        ACTION_NOT_SUPPORTED("SanitiseResponseHeader", @0);
      }
    | ACTION_SETENV run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetENV(std::move($2)));
      }
    | ACTION_SETRSC run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetRSC(std::move($2)));
      }
    | ACTION_SETSID run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetSID(std::move($2)));
      }
    | ACTION_SETUID run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetUID(std::move($2)));
      }
    | ACTION_SETVAR setvar_action
      {
        $$ = std::move($2);
      }
    | ACTION_SEVERITY
      {
        ACTION_CONTAINER($$, new actions::Severity($1));
      }
    | ACTION_SKIP
      {
        ACTION_CONTAINER($$, new actions::Skip($1));
      }
    | ACTION_SKIP_AFTER
      {
        ACTION_CONTAINER($$, new actions::SkipAfter($1));
      }
    | ACTION_STATUS
      {
        ACTION_CONTAINER($$, new actions::data::Status($1));
      }
    | ACTION_TAG run_time_string
      {
        ACTION_CONTAINER($$, new actions::Tag(std::move($2)));
      }
    | ACTION_VER
      {
        ACTION_CONTAINER($$, new actions::Ver($1));
      }
    | ACTION_XMLNS
      {
        ACTION_CONTAINER($$, new actions::XmlNS($1));
      }
    | ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT
      {
        ACTION_CONTAINER($$, new actions::transformations::ParityZero7bit($1));
      }
    | ACTION_TRANSFORMATION_PARITY_ODD_7_BIT
      {
        ACTION_CONTAINER($$, new actions::transformations::ParityOdd7bit($1));
      }
    | ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT
      {
        ACTION_CONTAINER($$, new actions::transformations::ParityEven7bit($1));
      }
    | ACTION_TRANSFORMATION_SQL_HEX_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::SqlHexDecode($1));
      }
      | ACTION_TRANSFORMATION_BASE_64_ENCODE
      {
        ACTION_CONTAINER($$, new actions::transformations::Base64Encode($1));
      }
    | ACTION_TRANSFORMATION_BASE_64_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::Base64Decode($1));
      }
   | ACTION_TRANSFORMATION_BASE_64_DECODE_EXT
      {
        ACTION_CONTAINER($$, new actions::transformations::Base64DecodeExt($1));
      }
    | ACTION_TRANSFORMATION_CMD_LINE
      {
        ACTION_CONTAINER($$, new actions::transformations::CmdLine($1));
      }
    | ACTION_TRANSFORMATION_SHA1
      {
        ACTION_CONTAINER($$, new actions::transformations::Sha1($1));
      }
    | ACTION_TRANSFORMATION_MD5
      {
        ACTION_CONTAINER($$, new actions::transformations::Md5($1));
      }
    | ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE 
      {
        ACTION_CONTAINER($$, new actions::transformations::EscapeSeqDecode($1));
      }
    | ACTION_TRANSFORMATION_HEX_ENCODE
      {
        ACTION_CONTAINER($$, new actions::transformations::HexEncode($1));
      }
    | ACTION_TRANSFORMATION_HEX_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::HexDecode($1));
      }
    | ACTION_TRANSFORMATION_LOWERCASE
      {
        ACTION_CONTAINER($$, new actions::transformations::LowerCase($1));
      }
    | ACTION_TRANSFORMATION_UPPERCASE
      {
        ACTION_CONTAINER($$, new actions::transformations::UpperCase($1));
      }
    | ACTION_TRANSFORMATION_URL_DECODE_UNI
      {
        ACTION_CONTAINER($$, new actions::transformations::UrlDecodeUni($1));
      }
    | ACTION_TRANSFORMATION_URL_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::UrlDecode($1));
      }
    | ACTION_TRANSFORMATION_URL_ENCODE
      {
        ACTION_CONTAINER($$, new actions::transformations::UrlEncode($1));
      }
    | ACTION_TRANSFORMATION_NONE
      {
        ACTION_CONTAINER($$, new actions::transformations::None($1));
      }
    | ACTION_TRANSFORMATION_COMPRESS_WHITESPACE
      {
        ACTION_CONTAINER($$, new actions::transformations::CompressWhitespace($1));
      }
    | ACTION_TRANSFORMATION_REMOVE_WHITESPACE
      {
        ACTION_CONTAINER($$, new actions::transformations::RemoveWhitespace($1));
      }
    | ACTION_TRANSFORMATION_REPLACE_NULLS
      {
        ACTION_CONTAINER($$, new actions::transformations::ReplaceNulls($1));
      }
    | ACTION_TRANSFORMATION_REMOVE_NULLS
      {
        ACTION_CONTAINER($$, new actions::transformations::RemoveNulls($1));
      }
    | ACTION_TRANSFORMATION_HTML_ENTITY_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::HtmlEntityDecode($1));
      }
    | ACTION_TRANSFORMATION_JS_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::JsDecode($1));
      }
    | ACTION_TRANSFORMATION_CSS_DECODE
      {
        ACTION_CONTAINER($$, new actions::transformations::CssDecode($1));
      }
    | ACTION_TRANSFORMATION_TRIM
      {
        ACTION_CONTAINER($$, new actions::transformations::Trim($1));
      }
    | ACTION_TRANSFORMATION_TRIM_LEFT
      {
        ACTION_CONTAINER($$, new actions::transformations::TrimLeft($1));
      }
    | ACTION_TRANSFORMATION_TRIM_RIGHT
      {
        ACTION_CONTAINER($$, new actions::transformations::TrimRight($1));
      }
    | ACTION_TRANSFORMATION_NORMALISE_PATH_WIN
      {
        ACTION_CONTAINER($$, new actions::transformations::NormalisePathWin($1));
      }
    | ACTION_TRANSFORMATION_NORMALISE_PATH
      {
        ACTION_CONTAINER($$, new actions::transformations::NormalisePath($1));
      }
    | ACTION_TRANSFORMATION_LENGTH
      {
        ACTION_CONTAINER($$, new actions::transformations::Length($1));
      }
    | ACTION_TRANSFORMATION_UTF8_TO_UNICODE
      {
        ACTION_CONTAINER($$, new actions::transformations::Utf8ToUnicode($1));
      }
    | ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR
      {
        ACTION_CONTAINER($$, new actions::transformations::RemoveCommentsChar($1));
      }
    | ACTION_TRANSFORMATION_REMOVE_COMMENTS
      {
        ACTION_CONTAINER($$, new actions::transformations::RemoveComments($1));
      }
    | ACTION_TRANSFORMATION_REPLACE_COMMENTS
      {
        ACTION_CONTAINER($$, new actions::transformations::ReplaceComments($1));
      }
    ;

setvar_action:
    NOT var
      {
        ACTION_CONTAINER($$, new actions::SetVar(actions::SetVarOperation::unsetOperation, std::move($2)));
      }
    | var
      {
        ACTION_CONTAINER($$, new actions::SetVar(actions::SetVarOperation::setToOneOperation, std::move($1)));
      }
    | var SETVAR_OPERATION_EQUALS run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetVar(actions::SetVarOperation::setOperation, std::move($1), std::move($3)));
      }
    | var SETVAR_OPERATION_EQUALS_PLUS run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetVar(actions::SetVarOperation::sumAndSetOperation, std::move($1), std::move($3)));
      }
    | var SETVAR_OPERATION_EQUALS_MINUS run_time_string
      {
        ACTION_CONTAINER($$, new actions::SetVar(actions::SetVarOperation::substractAndSetOperation, std::move($1), std::move($3)));
      }
    ;

run_time_string:
    run_time_string FREE_TEXT_QUOTE_MACRO_EXPANSION
      {
        $1->appendText($2);
        $$ = std::move($1);
      }
    | run_time_string var
      {
        $1->appendVar(std::move($2));
        $$ = std::move($1);
      }
    | FREE_TEXT_QUOTE_MACRO_EXPANSION
      {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendText($1);
        $$ = std::move(r);
      }
    | var
      {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendVar(std::move($1));
        $$ = std::move(r);
      }
    ;
%%

void yy::seclang_parser::error (const location_type& l, const std::string& m) {
    driver.error (l, m);
}
