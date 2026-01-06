%{ /* -*- C++ -*- */
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <string>

#include "src/parser/driver.h"
#include "src/parser/seclang-parser.hh"
#include "src/utils/https_client.h"
#include "src/utils/string.h"

using modsecurity::Parser::Driver;
using modsecurity::Utils::HttpsClient;
using modsecurity::utils::string::parserSanitizer;

typedef yy::seclang_parser p;
static int state_variable_from = 0;
static std::stack<int> YY_PREVIOUS_STATE;

// Work around an incompatibility in flex (at least versions
// 2.5.31 through 2.5.33): it generates code that does
// not conform to C89.  See Debian bug 333231
// <http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=333231>.
# undef yywrap
# define yywrap() 1

#define BEGINX(z) { \
    YY_PREVIOUS_STATE.push(YY_START); \
    BEGIN(z); \
}

#define BEGINX_() { \
    YY_PREVIOUS_STATE.push(YY_START); \
    if (YY_START == SETVAR_ACTION_NONQUOTED) { \
        BEGIN(EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED); \
    } else if (YY_START == SETVAR_ACTION_QUOTED) { \
        BEGIN(EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED); \
    } else { \
        BEGIN(EXPECTING_VAR_PARAMETER); \
    } \
}

#define BEGIN_PARAMETER() { if (YY_START == EXPECTING_OPERATOR_ENDS_WITH_SPACE) { BEGIN(TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_SPACE); } else { BEGIN(TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_QUOTE); } }
#define BEGIN_NO_OP_INFORMED() { if (YY_START == EXPECTING_OPERATOR_ENDS_WITH_SPACE) { BEGIN(NO_OP_INFORMED_ENDS_WITH_SPACE); } else { BEGIN(NO_OP_INFORMED_ENDS_WITH_QUOTE); } }

#define BEGIN_ACTION_OPERATION() { \
    if (YY_START == SETVAR_ACTION_NONQUOTED) { \
        BEGIN(SETVAR_ACTION_NONQUOTED_WAITING_OPERATION); \
    } else if (YY_START == SETVAR_ACTION_QUOTED) { \
        BEGIN(SETVAR_ACTION_QUOTED_WAITING_OPERATION); \
    } else if (YY_START == SETVAR_ACTION_NONQUOTED_WAITING_COLLECTION_ELEM) { \
        BEGIN(SETVAR_ACTION_NONQUOTED_WAITING_OPERATION); \
    } else if (YY_START == SETVAR_ACTION_QUOTED_WAITING_COLLECTION_ELEM) { \
        BEGIN(SETVAR_ACTION_QUOTED_WAITING_OPERATION); \
    }\
}


#define BEGIN_ACTION_WAITING_CONTENT() { \
    if (YY_START == SETVAR_ACTION_NONQUOTED_WAITING_OPERATION) { \
        BEGIN(SETVAR_ACTION_NONQUOTED_WAITING_CONTENT); \
    } else if (YY_START == SETVAR_ACTION_QUOTED_WAITING_OPERATION) { \
        BEGIN(SETVAR_ACTION_QUOTED_WAITING_CONTENT); \
    } else if (YY_START == EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED) { \
        BEGIN(SETVAR_ACTION_QUOTED_WAITING_CONTENT); \
    } else if (YY_START == EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED) { \
        BEGIN(SETVAR_ACTION_NONQUOTED_WAITING_CONTENT); \
    } \
}


#define BEGIN_PREVIOUS() { BEGIN(YY_PREVIOUS_STATE.top()); YY_PREVIOUS_STATE.pop(); }

// The location of the current token.
%}
%option noyywrap nounput batch debug noinput nounistd never-interactive



ACTION_ACCURACY                                 (?i:accuracy)
ACTION_ALLOW                                    ((?i:allow:(?i:REQUEST|PHASE))|(?i:phase:'(?i:REQUEST|PHASE)')|(?i:allow))
ACTION_APPEND                                   (?i:append)
ACTION_AUDIT_LOG                                (?i:auditlog)
ACTION_BLOCK                                    (?i:block)
ACTION_CAPTURE                                  (?i:capture)
ACTION_CHAIN                                    (?i:chain)
ACTION_CTL_AUDIT_ENGINE                         (?i:ctl:auditEngine)
ACTION_CTL_AUDIT_LOG_PARTS                      (?i:ctl:auditLogParts)
ACTION_CTL_BDY_JSON                             (?i:ctl:requestBodyProcessor=JSON)
ACTION_CTL_BDY_XML                              (?i:ctl:requestBodyProcessor=XML)
ACTION_CTL_BDY_URLENCODED                       (?i:ctl:requestBodyProcessor=URLENCODED)
ACTION_CTL_FORCE_REQ_BODY_VAR                   (?i:ctl:forceRequestBodyVariable)
ACTION_CTL_PARSE_XML_INTO_ARGS                  (?i:ctl:parseXmlIntoArgs)
ACTION_CTL_REQUEST_BODY_ACCESS                  (?i:ctl:requestBodyAccess)
ACTION_CTL_RULE_ENGINE                          (?i:ctl:ruleEngine)
ACTION_CTL_RULE_REMOVE_BY_TAG                   (?i:ctl:ruleRemoveByTag)
ACTION_CTL_RULE_REMOVE_BY_ID                    (?i:ctl:ruleRemoveById)
ACTION_CTL_RULE_REMOVE_TARGET_BY_ID             (?i:ctl:ruleRemoveTargetById)
ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG            (?i:ctl:ruleRemoveTargetByTag)
ACTION_DENY                                     (?i:deny)
ACTION_DEPRECATE_VAR                            (?i:deprecatevar)
ACTION_DROP                                     (?i:drop)
ACTION_EXEC                                     (?i:exec)
ACTION_EXPIRE_VAR                               (?i:expirevar)
ACTION_ID                                       (?i:id:[0-9]+|id:'[0-9]+')
ACTION_INITCOL                                  (?i:initcol)
ACTION_LOG_DATA                                 (?i:logdata)
ACTION_LOG                                      (?i:log)
ACTION_MATURITY                                 (?i:maturity)
ACTION_MSG                                      (?i:msg)
ACTION_MULTI_MATCH                              (?i:multiMatch)
ACTION_NO_AUDIT_LOG                             (?i:noauditlog)
ACTION_NO_LOG                                   (?i:nolog)
ACTION_PASS                                     (?i:pass)
ACTION_PAUSE                                    (?i:pause)
ACTION_PHASE                                    ((?i:phase:(?i:REQUEST|RESPONSE|LOGGING|[0-9]+))|(?i:phase:'(?i:REQUEST|RESPONSE|LOGGING|[0-9]+)'))
ACTION_PREPEND                                  (?i:prepend)
ACTION_PROXY                                    (?i:proxy)
ACTION_REDIRECT                                 (?i:redirect)
ACTION_REV                                      (?i:rev)
ACTION_SANITISE_ARG                             (?i:sanitiseArg)
ACTION_SANITISE_MATCHED_BYTES                   (?i:sanitiseMatchedBytes)
ACTION_SANITISE_MATCHED                         (?i:sanitiseMatched)
ACTION_SANITISE_REQUEST_HEADER                  (?i:sanitiseRequestHeader)
ACTION_SANITISE_RESPONSE_HEADER                 (?i:sanitiseResponseHeader)
ACTION_SETENV                                   (?i:setenv)
ACTION_SETRSC                                   (?i:setrsc)
ACTION_SETSID                                   (?i:setsid)
ACTION_SETUID                                   (?i:setuid)
ACTION_SETVAR                                   (?i:setvar)
ACTION_SEVERITY                                 (?i:severity)
ACTION_SEVERITY_VALUE                           (?i:(EMERGENCY|ALERT|CRITICAL|ERROR|WARNING|NOTICE|INFO|DEBUG)|[0-9]+)
ACTION_SKIP_AFTER                               (?i:skipAfter)
ACTION_SKIP                                     (?i:skip)
ACTION_STATUS                                   (?i:status:[0-9]+)
ACTION_TAG                                      (?i:tag)
ACTION_VER                                      (?i:ver)
ACTION_XMLNS                                    (?i:xmlns)            
ACTION_TRANSFORMATION_BASE_64_ENCODE            (?i:t:base64Encode)
ACTION_TRANSFORMATION_BASE_64_DECODE            (?i:t:base64Decode)
ACTION_TRANSFORMATION_BASE_64_DECODE_EXT        (?i:t:base64DecodeExt)
ACTION_TRANSFORMATION_CMD_LINE                  (?i:t:cmdLine)
ACTION_TRANSFORMATION_COMPRESS_WHITESPACE       (?i:t:compressWhitespace)
ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE         (?i:t:escapeSeqDecode)
ACTION_TRANSFORMATION_CSS_DECODE                (?i:t:cssDecode)
ACTION_TRANSFORMATION_HEX_ENCODE                (?i:t:hexEncode)
ACTION_TRANSFORMATION_HEX_DECODE                (?i:t:hexDecode)
ACTION_TRANSFORMATION_HTML_ENTITY_DECODE        (?i:t:htmlEntityDecode)
ACTION_TRANSFORMATION_JS_DECODE                 (?i:t:jsDecode)
ACTION_TRANSFORMATION_LENGTH                    (?i:t:length)
ACTION_TRANSFORMATION_LOWERCASE                 (?i:t:lowercase)
ACTION_TRANSFORMATION_MD5                       (?i:t:md5)
ACTION_TRANSFORMATION_NONE                      (?i:t:none)
ACTION_TRANSFORMATION_NORMALISE_PATH            (?i:t:(normalisePath|normalizePath))
ACTION_TRANSFORMATION_NORMALISE_PATH_WIN        (?i:t:(normalisePathWin|normalizePathWin))
ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT         (?i:t:parityEven7bit)
ACTION_TRANSFORMATION_PARITY_ODD_7_BIT          (?i:t:parityOdd7bit)
ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT         (?i:t:parityZero7bit)
ACTION_TRANSFORMATION_REMOVE_COMMENTS           (?i:t:removeComments)
ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR      (?i:t:removeCommentsChar)
ACTION_TRANSFORMATION_REMOVE_NULLS              (?i:t:removeNulls)
ACTION_TRANSFORMATION_REMOVE_WHITESPACE         (?i:t:removeWhitespace)
ACTION_TRANSFORMATION_REPLACE_COMMENTS          (?i:t:replaceComments)
ACTION_TRANSFORMATION_REPLACE_NULLS             (?i:t:replaceNulls)
ACTION_TRANSFORMATION_SHA1                      (?i:t:sha1)
ACTION_TRANSFORMATION_SQL_HEX_DECODE            (?i:t:sqlHexDecode)
ACTION_TRANSFORMATION_TRIM                      (?i:t:trim)
ACTION_TRANSFORMATION_TRIM_LEFT                 (?i:t:trimLeft)
ACTION_TRANSFORMATION_TRIM_RIGHT                (?i:t:trimRight)
ACTION_TRANSFORMATION_UPPERCASE                 (?i:t:uppercase)
ACTION_TRANSFORMATION_URL_ENCODE                (?i:t:urlEncode)
ACTION_TRANSFORMATION_URL_DECODE                (?i:t:urlDecode)
ACTION_TRANSFORMATION_URL_DECODE_UNI            (?i:t:urlDecodeUni)
ACTION_TRANSFORMATION_UTF8_TO_UNICODE           (?i:t:utf8toUnicode)


VARIABLE_ARGS_COMBINED_SIZE               (?i:ARGS_COMBINED_SIZE)
VARIABLE_ARGS_GET_NAMES                   (?i:ARGS_GET_NAMES)
VARIABLE_ARGS_NAMES                       (?i:ARGS_NAMES)
VARIABLE_ARGS_POST_NAMES                  (?i:ARGS_POST_NAMES)
VARIABLE_AUTH_TYPE                        (?i:AUTH_TYPE)
VARIABLE_FILES_COMBINED_SIZE              (?i:FILES_COMBINED_SIZE)
VARIABLE_FILES_TMP_NAMES                  (?i:FILES_TMPNAMES)
VARIABLE_FULL_REQUEST                     (?i:FULL_REQUEST)
VARIABLE_FULL_REQUEST_LENGTH              (?i:FULL_REQUEST_LENGTH)
VARIABLE_GLOBAL                           (?i:GLOBAL)
VARIABLE_INBOUND_DATA_ERROR               (?i:INBOUND_DATA_ERROR)
VARIABLE_MATCHED_VAR                      (?i:MATCHED_VAR)
VARIABLE_MATCHED_VAR_NAME                 (?i:MATCHED_VAR_NAME)
VARIABLE_MSC_PCRE_ERROR                   (?i:MSC_PCRE_ERROR)
VARIABLE_MSC_PCRE_LIMITS_EXCEEDED         (?i:MSC_PCRE_LIMITS_EXCEEDED)
VARIABLE_MULTIPART_BOUNDARY_QUOTED        (?i:MULTIPART_BOUNDARY_QUOTED)
VARIABLE_MULTIPART_BOUNDARY_WHITESPACE    (?i:MULTIPART_BOUNDARY_WHITESPACE)
VARIABLE_MULTIPART_CRLF_LF_LINES          (?i:MULTIPART_CRLF_LF_LINES)
VARIABLE_MULTIPART_DATA_AFTER             (?i:MULTIPART_DATA_AFTER)
VARIABLE_MULTIPART_DATA_BEFORE            (?i:MULTIPART_DATA_BEFORE)
VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED    (?i:MULTIPART_FILE_LIMIT_EXCEEDED)
VARIABLE_MULTIPART_FILENAME               (?i:MULTIPART_FILENAME)
VARIABLE_MULTIPART_HEADER_FOLDING         (?i:MULTIPART_HEADER_FOLDING)
VARIABLE_MULTIPART_INVALID_HEADER_FOLDING (?i:MULTIPART_INVALID_HEADER_FOLDING)
VARIABLE_MULTIPART_INVALID_PART           (?i:MULTIPART_INVALID_PART)
VARIABLE_MULTIPART_INVALID_QUOTING        (?i:MULTIPART_INVALID_QUOTING)
VARIABLE_MULTIPART_LF_LINE                (?i:MULTIPART_LF_LINE)
VARIABLE_MULTIPART_MISSING_SEMICOLON      (?i:MULTIPART_MISSING_SEMICOLON)
VARIABLE_MULTIPART_SEMICOLON_MISSING      (?i:MULTIPART_SEMICOLON_MISSING)
VARIABLE_MULTIPART_NAME                   (?i:MULTIPART_NAME)
VARIABLE_MULTIPART_STRICT_ERROR           (?i:MULTIPART_STRICT_ERROR)
VARIABLE_MULTIPART_UNMATCHED_BOUNDARY     (?i:MULTIPART_UNMATCHED_BOUNDARY)
VARIABLE_OUTBOUND_DATA_ERROR              (?i:OUTBOUND_DATA_ERROR)
VARIABLE_PATH_INFO                        (?i:PATH_INFO)
VARIABLE_QUERY_STRING                     (?i:QUERY_STRING)
VARIABLE_REMOTE_ADDR                      (?i:REMOTE_ADDR)
VARIABLE_REMOTE_HOST                      (?i:REMOTE_HOST)
VARIABLE_REMOTE_PORT                      (?i:REMOTE_PORT)
VARIABLE_REQBODY_ERROR                    (?i:REQBODY_ERROR)
VARIABLE_REQBODY_ERROR_MSG                (?i:REQBODY_ERROR_MSG)
VARIABLE_REQBODY_PROCESSOR_ERROR          (?i:REQBODY_PROCESSOR_ERROR)
VARIABLE_REQBODY_PROCESSOR_ERROR_MSG      (?i:REQBODY_PROCESSOR_ERROR_MSG)
VARIABLE_REQBODY_PROCESSOR                (?i:REQBODY_PROCESSOR)
VARIABLE_REQUEST_BASENAME                 (?i:REQUEST_BASENAME)
VARIABLE_REQUEST_BODY                     (?i:REQUEST_BODY)
VARIABLE_REQUEST_BODY_LENGTH              (?i:REQUEST_BODY_LENGTH)
VARIABLE_REQUEST_FILE_NAME                (?i:REQUEST_FILENAME)
VARIABLE_REQUEST_HEADERS_NAMES            (?i:REQUEST_HEADERS_NAMES)
VARIABLE_REQUEST_LINE                     (?i:REQUEST_LINE)
VARIABLE_REQUEST_METHOD                   (?i:REQUEST_METHOD)
VARIABLE_REQUEST_PROTOCOL                 (?i:REQUEST_PROTOCOL)
VARIABLE_REQUEST_URI                      (?i:REQUEST_URI)
VARIABLE_REQUEST_URI_RAW                  (?i:REQUEST_URI_RAW)
VARIABLE_RESOURCE                         (?i:RESOURCE)
VARIABLE_RESPONSE_BODY                    (?i:RESPONSE_BODY)
VARIABLE_RESPONSE_CONTENT_LENGTH          (?i:RESPONSE_CONTENT_LENGTH)
VARIABLE_RESPONSE_CONTENT_TYPE            (?i:RESPONSE_CONTENT_TYPE)
VARIABLE_RESPONSE_HEADERS_NAMES           (?i:RESPONSE_HEADERS_NAMES)
VARIABLE_RESPONSE_PROTOCOL                (?i:RESPONSE_PROTOCOL)
VARIABLE_RESPONSE_STATUS                  (?i:RESPONSE_STATUS)
VARIABLE_SERVER_ADDR                      (?i:SERVER_ADDR)
VARIABLE_SERVER_NAME                      (?i:SERVER_NAME)
VARIABLE_SERVER_PORT                      (?i:SERVER_PORT)
VARIABLE_SESSION_ID                       (?i:SESSIONID)
VARIABLE_UNIQUE_ID                        (?i:UNIQUE_ID)
VARIABLE_URL_ENCODED_ERROR                (?i:URLENCODED_ERROR)
VARIABLE_USER_ID                          (?i:USERID)
VARIABLE_WEBSERVER_ERROR_LOG              (?i:WEBSERVER_ERROR_LOG)
VARIABLE_ARGS                             (?i:ARGS)
VARIABLE_ARGS_POST                        (?i:ARGS_POST)
VARIABLE_ARGS_GET                         (?i:ARGS_GET)
VARIABLE_FILES_SIZES                      (?i:FILES_SIZES)
VARIABLE_FILES_NAMES                      (?i:FILES_NAMES)
VARIABLE_FILES_TMP_CONTENT                (?i:FILES_TMP_CONTENT)
VARIABLE_MATCHED_VARS_NAMES               (?i:MATCHED_VARS_NAMES)
VARIABLE_MATCHED_VARS                     (?i:MATCHED_VARS)
VARIABLE_FILES                            (?i:FILES)
VARIABLE_REQUEST_COOKIES                  (?i:REQUEST_COOKIES)
VARIABLE_REQUEST_HEADERS                  (?i:REQUEST_HEADERS)
VARIABLE_RESPONSE_HEADERS                 (?i:RESPONSE_HEADERS)
VARIABLE_GEO                              (?i:GEO)
VARIABLE_REQUEST_COOKIES_NAMES            (?i:REQUEST_COOKIES_NAMES)
VARIABLE_MULTIPART_PART_HEADERS           (?i:MULTIPART_PART_HEADERS)
VARIABLE_RULE                             (?i:RULE)
VARIABLE_SESSION                          (?i:(SESSION))
VARIABLE_IP                               (?i:(IP))
VARIABLE_USER                             (?i:(USER))
VARIABLE_STATUS                           (?i:(STATUS))
VARIABLE_STATUS_LINE                      (?i:(STATUS_LINE))
VARIABLE_TX                               (?i:TX)
VARIABLE_WEB_APP_ID                       (?i:WEBAPPID)
RUN_TIME_VAR_BLD                          (?i:MODSEC_BUILD)
RUN_TIME_VAR_DUR                          (?i:DURATION)
RUN_TIME_VAR_ENV                          (?i:ENV)
RUN_TIME_VAR_HSV                          (?i:HIGHEST_SEVERITY)
RUN_TIME_VAR_REMOTE_USER                  (?i:REMOTE_USER)
RUN_TIME_VAR_TIME                         (?i:TIME)
RUN_TIME_VAR_TIME_DAY                     (?i:TIME_DAY)
RUN_TIME_VAR_TIME_EPOCH                   (?i:TIME_EPOCH)
RUN_TIME_VAR_TIME_HOUR                    (?i:TIME_HOUR)
RUN_TIME_VAR_TIME_MIN                     (?i:TIME_MIN)
RUN_TIME_VAR_TIME_MON                     (?i:TIME_MON)
RUN_TIME_VAR_TIME_SEC                     (?i:TIME_SEC)
RUN_TIME_VAR_TIME_WDAY                    (?i:TIME_WDAY)
RUN_TIME_VAR_TIME_YEAR                    (?i:TIME_YEAR)
RUN_TIME_VAR_XML                          (?i:XML)
VAR_EXCLUSION                             !
VAR_COUNT                                 &


OPERATOR_BEGINS_WITH                    (?i:@beginsWith)
OPERATOR_CONTAINS                       (?i:@contains)
OPERATOR_CONTAINS_WORD                  (?i:@containsWord)
OPERATOR_DETECT_SQLI                    (?i:@detectSQLi)
OPERATOR_DETECT_XSS                     (?i:@detectXSS)
OPERATOR_ENDS_WITH                      (?i:@endsWith)
OPERATOR_EQ                             (?i:@eq)
OPERATOR_FUZZY_HASH                     (?i:@fuzzyHash)
OPERATOR_GE                             (?i:@ge)
OPERATOR_GEOLOOKUP                      (?i:@geoLookup)
OPERATOR_GSB_LOOKUP                     (?i:@gsbLookup)
OPERATOR_GT                             (?i:@gt)
OPERATOR_INSPECT_FILE                   (?i:@inspectFile)
OPERATOR_IP_MATCH_FROM_FILE             (?i:(@ipMatchF|@ipMatchFromFile))
OPERATOR_IP_MATCH                       (?i:@ipMatch)
OPERATOR_LE                             (?i:@le)
OPERATOR_LT                             (?i:@lt)
OPERATOR_PM_FROM_FILE                   (?i:(@pmf|@pmFromFile))
OPERATOR_PM                             (?i:@pm)
OPERATOR_RBL                            (?i:@rbl)
OPERATOR_RSUB                           (?i:@rsub)
OPERATOR_RX                             (?i:@rx)
OPERATOR_RX_GLOBAL                      (?i:@rxGlobal)
OPERATOR_STR_EQ                         (?i:@streq)
OPERATOR_STR_MATCH                      (?i:@strmatch)
OPERATOR_UNCONDITIONAL_MATCH            (?i:@unconditionalMatch)
OPERATOR_VALIDATE_BYTE_RANGE            (?i:@validateByteRange)
OPERATOR_VALIDATE_DTD                   (?i:@validateDTD)
OPERATOR_VALIDATE_HASH                  (?i:@validateHash)
OPERATOR_VALIDATE_SCHEMA                (?i:@validateSchema)
OPERATOR_VALIDATE_URL_ENCODING          (?i:@validateUrlEncoding)
OPERATOR_VALIDATE_UTF8_ENCODING         (?i:@validateUtf8Encoding)
OPERATOR_VERIFY_CC                      (?i:@verifyCC)
OPERATOR_VERIFY_CPF                     (?i:@verifyCPF)
OPERATOR_VERIFY_SSN                     (?i:@verifySSN)
OPERATOR_VERIFY_SVNR                    (?i:@verifySVNR)
OPERATOR_WITHIN                         (?i:@within)


AUDIT_PARTS                             [ABCDEFGHJKIZ]+
COL_FREE_TEXT_SPACE_COMMA               ([^,"])+
COL_NAME                                [A-Za-z]+
CONFIG_COMPONENT_SIG                    (?i:SecComponentSignature)
CONFIG_SEC_SERVER_SIG                   (?i:SecServerSignature)
CONFIG_SEC_WEB_APP_ID                   (?i:SecWebAppId)
CONFIG_SEC_CACHE_TRANSFORMATIONS        (?i:SecCacheTransformations)
CONFIG_SEC_CHROOT_DIR                   (?i:SecChrootDir)
CONFIG_CONN_ENGINE                      (?i:SecConnEngine)
CONFIG_SEC_HASH_ENGINE                  (?i:SecHashEngine)
CONFIG_SEC_HASH_KEY                     (?i:SecHashKey)
CONFIG_SEC_HASH_PARAM                   (?i:SecHashParam)
CONFIG_SEC_HASH_METHOD_RX               (?i:SecHashMethodRx)
CONFIG_SEC_HASH_METHOD_PM               (?i:SecHashMethodPm)
CONFIG_CONTENT_INJECTION                (?i:SecContentInjection)
CONFIG_SEC_ARGUMENT_SEPARATOR           (?i:SecArgumentSeparator)
CONFIG_DIR_AUDIT_DIR                    (?i:SecAuditLogStorageDir)
CONFIG_DIR_AUDIT_DIR_MOD                (?i:SecAuditLogDirMode)
CONFIG_DIR_AUDIT_ENG                    (?i:SecAuditEngine)
CONFIG_DIR_AUDIT_FLE_MOD                (?i:SecAuditLogFileMode)
CONFIG_DIR_AUDIT_LOG2                   (?i:SecAuditLog2)
CONFIG_DIR_AUDIT_LOG                    (?i:SecAuditLog)
CONFIG_DIR_AUDIT_LOG_FMT                (?i:SecAuditLogFormat)
CONFIG_DIR_AUDIT_PREFIX                 (?i:SecAuditLogPrefix)
CONFIG_DIR_AUDIT_LOG_P                  (?i:SecAuditLogParts)
CONFIG_DIR_AUDIT_STS                    (?i:SecAuditLogRelevantStatus)
CONFIG_DIR_AUDIT_TPE                    (?i:SecAuditLogType)
CONFIG_DIR_DEBUG_LOG                    (?i:SecDebugLog)
CONFIG_DIR_DEBUG_LVL                    (?i:SecDebugLogLevel)
CONFIG_DIR_GEO_DB                       (?i:SecGeoLookupDb)
CONFIG_DIR_GSB_DB                       (?i:SecGsbLookupDb)
CONFIG_SEC_GUARDIAN_LOG                 (?i:SecGuardianLog)
CONFIG_SEC_INTERCEPT_ON_ERROR           (?i:SecInterceptOnError)
CONFIG_SEC_CONN_R_STATE_LIMIT           (?i:SecConnReadStateLimit)
CONFIG_SEC_CONN_W_STATE_LIMIT           (?i:SecConnWriteStateLimit)
CONFIG_SEC_SENSOR_ID                    (?i:SecSensorId)
CONFIG_SEC_RULE_INHERITANCE             (?i:SecRuleInheritance)
CONFIG_SEC_RULE_PERF_TIME               (?i:SecRulePerfTime)
CONFIG_SEC_STREAM_IN_BODY_INSPECTION    (?i:SecStreamInBodyInspection)
CONFIG_SEC_STREAM_OUT_BODY_INSPECTION   (?i:SecStreamOutBodyInspection)
CONFIG_DIR_PCRE_MATCH_LIMIT             (?i:SecPcreMatchLimit)
CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION   (?i:SecPcreMatchLimitRecursion)
CONFIG_DIR_ARGS_LIMIT                   (?i:SecArgumentsLimit)
CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT    (?i:SecRequestBodyJsonDepthLimit)
CONFIG_DIR_REQ_BODY                     (?i:SecRequestBodyAccess)
CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT     (?i:SecRequestBodyInMemoryLimit)
CONFIG_DIR_REQ_BODY_LIMIT               (?i:SecRequestBodyLimit)
CONFIG_DIR_REQ_BODY_LIMIT_ACTION        (?i:SecRequestBodyLimitAction)
CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT      (?i:SecRequestBodyNoFilesLimit)
CONFIG_DIR_RES_BODY                     (?i:SecResponseBodyAccess)
CONFIG_DIR_RES_BODY_LIMIT               (?i:SecResponseBodyLimit)
CONFIG_DIR_RES_BODY_LIMIT_ACTION        (?i:SecResponseBodyLimitAction)
CONFIG_DIR_RULE_ENG                     (?i:SecRuleEngine)
CONFIG_DIR_SEC_ACTION                   (?i:SecAction)
CONFIG_DIR_SEC_DEFAULT_ACTION           (?i:SecDefaultAction)
CONFIG_SEC_DISABLE_BACKEND_COMPRESS     (?i:SecDisableBackendCompression)
CONFIG_DIR_SEC_MARKER                   (?i:SecMarker)
CONFIG_DIR_UNICODE_MAP_FILE             (?i:SecUnicodeMapFile)
CONFIG_INCLUDE                          (?i:Include)
CONFIG_SEC_COLLECTION_TIMEOUT           (?i:SecCollectionTimeout)
CONFIG_SEC_HTTP_BLKEY                   (?i:SecHttpBlKey)
CONFIG_SEC_REMOTE_RULES                 (?i:SecRemoteRules)
CONFIG_SEC_REMOTE_RULES_FAIL_ACTION     (?i:SecRemoteRulesFailAction)
CONFIG_SEC_REMOVE_RULES_BY_ID           (?i:SecRuleRemoveById)
CONFIG_SEC_REMOVE_RULES_BY_MSG          (?i:SecRuleRemoveByMsg)
CONFIG_SEC_REMOVE_RULES_BY_TAG          (?i:SecRuleRemoveByTag)
CONFIG_SEC_UPDATE_TARGET_BY_TAG         (?i:SecRuleUpdateTargetByTag)
CONFIG_SEC_UPDATE_TARGET_BY_MSG         (?i:SecRuleUpdateTargetByMsg)
CONFIG_SEC_UPDATE_TARGET_BY_ID          (?i:SecRuleUpdateTargetById)
CONFIG_SEC_UPDATE_ACTION_BY_ID          (?i:SecRuleUpdateActionById)
CONFIG_UPDLOAD_KEEP_FILES               (?i:SecUploadKeepFiles)
CONFIG_UPDLOAD_SAVE_TMP_FILES           (?i:SecTmpSaveUploadedFiles)
CONFIG_UPLOAD_DIR                       (?i:SecUploadDir)
CONFIG_UPLOAD_FILE_LIMIT                (?i:SecUploadFileLimit)
CONFIG_UPLOAD_FILE_MODE                 (?i:SecUploadFileMode)
CONFIG_VALUE_ABORT                      (?i:Abort)
CONFIG_VALUE_DETC                       (?i:DetectionOnly)
CONFIG_VALUE_HTTPS                      (?i:https)
CONFIG_VALUE_NUMBER                     [0-9]+
CONFIG_VALUE_ONLYARGS                   (?i:OnlyArgs)
CONFIG_VALUE_OFF                        (?i:Off)
CONFIG_VALUE_ON                         (?i:On)
CONFIG_VALUE_PARALLEL                   (?i:Parallel|Concurrent)
CONFIG_VALUE_PATH                       (?i:[0-9a-z_/.*: \\()-]+)
CONFIG_VALUE_PROCESS_PARTIAL            (?i:ProcessPartial)
CONFIG_VALUE_REJECT                     (?i:Reject)
CONFIG_VALUE_RELEVANT_ONLY              (?i:RelevantOnly)
CONFIG_VALUE_SERIAL                     (?i:Serial)
CONFIG_VALUE_WARN                       (?i:Warn)
CONFIG_XML_EXTERNAL_ENTITY              (?i:SecXmlExternalEntity)
CONFIG_XML_PARSE_XML_INTO_ARGS          (?i:SecParseXmlIntoArgs)
CONGIG_DIR_RESPONSE_BODY_MP             (?i:SecResponseBodyMimeType)
CONGIG_DIR_RESPONSE_BODY_MP_CLEAR       (?i:SecResponseBodyMimeTypesClear)
CONGIG_DIR_SEC_ARG_SEP                  (?i:SecArgumentSeparator)
CONGIG_DIR_SEC_COOKIE_FORMAT            (?i:SecCookieFormat)
CONFIG_SEC_COOKIEV0_SEPARATOR           (?i:SecCookieV0Separator)
CONGIG_DIR_SEC_DATA_DIR                 (?i:SecDataDir)
CONGIG_DIR_SEC_STATUS_ENGINE            (?i:SecStatusEngine)
CONGIG_DIR_SEC_TMP_DIR                  (?i:SecTmpDir)
DICT_ELEMENT                            ([^\"|,\n \t}=]|([^\\]\\\"))+
DICT_ELEMENT_WITH_PIPE                  [^ =\t"]+
DICT_ELEMENT_NO_PIPE                    [^ =\|\t"]+
DICT_ELEMENT_NO_MACRO                   ([^\"|,%{\n \t}=]|([^\\]\\\"))+
DICT_ELEMENT_WITH_EQUALS                ([^\"|,\n \t}]|([^\\]\\\"))+

DIRECTIVE                               (?i:SecRule)
DIRECTIVE_SECRULESCRIPT                 (?i:SecRuleScript)
FREE_TEXT_NEW_LINE                      [^\"|\n]+
FREE_TEXT_QUOTE                         ([^\']|([^\\]\\\'))+
QUOTE_BUT_SCAPED                        (')
DOUBLE_QUOTE_BUT_SCAPED                 (")
COMMA_BUT_SCAPED                        (,)
FREE_TEXT_QUOTE_MACRO_EXPANSION                 (([^%'])|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\][']|[^\\]([\\][\\])+[\\]['])+
FREE_TEXT_DOUBLE_QUOTE_MACRO_EXPANSION          ((([^"%])|([%][^{]))|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\]["]|[^\\]([\\][\\])+[\\]["])+
FREE_TEXT_EQUALS_MACRO_EXPANSION                ((([^",=%])|([%][^{]))|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\][=]|[^\\]([\\][\\])+[\\][=])+
FREE_TEXT_EQUALS_QUOTE_MACRO_EXPANSION          ((([^'",=%])|([%][^{]))|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\][=]|[^\\][\\][']|[^\\]([\\][\\])+[\\][=])+
FREE_TEXT_COMMA_MACRO_EXPANSION                 (([^%,])|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\][,]|[^\\]([\\][\\])+[\\][,])+
FREE_TEXT_COMMA_DOUBLE_QUOTE_MACRO_EXPANSION    ((([^,"%])|([%][^{]))|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\]["]|[^\\]([\\][\\])+[\\]["])+

FREE_TEXT_SPACE_MACRO_EXPANSION         (([^% ])|([^\\][\\][%][{])|([^\\]([\\][\\])+[\\][%][{])|[^\\][\\][ ]|[^\\]([\\][\\])+[\\][ ])+
START_MACRO_VARIABLE                    (\%\{)
FREE_TEXT_QUOTE_COMMA                   [^,\']+
FREE_TEXT_SPACE                         [^ \t]+
FREE_TEXT_SPACE_COMMA                   [^, \t]+
FREE_TEXT_SPACE_COMMA_QUOTE             [^, \t\"\n\r]+
FREE_TEXT_COMMA_QUOTE                   [^,\"\\n\\r]+
NEW_LINE_FREE_TEXT                      [^, \t\"\n\r]+
NOT !
FREE_TEXT                               ([^\"]|([^\\]\\\"))+
REMOVE_RULE_BY                          [0-9A-Za-z_\/\.\-\*\:\;\]\[\$]+

VAR_FREE_TEXT_QUOTE                     ([^\']|([^\\]\\\'))+
VAR_FREE_TEXT_SPACE                     [^ \t\"]+
VAR_FREE_TEXT_SPACE_COMMA               [^, \t\"]+

JSON                                    (?i:JSON)
NATIVE                                  (?i:NATIVE)

NEW_LINE                                [\n\r]+

EQUALS                                  (?i:=)
EQUALS_PLUS                             (?i:=\+)
EQUALS_MINUS                            (?i:=\-)

%x EXPECTING_ACTION_PREDICATE_VARIABLE
%x TRANSACTION_TO_VARIABLE
%x EXPECTING_VARIABLE
%x EXPECTING_OPERATOR_ENDS_WITH_SPACE EXPECTING_OPERATOR_ENDS_WITH_QUOTE
%x EXPECTING_ACTION_PREDICATE ACTION_PREDICATE_ENDS_WITH_QUOTE ACTION_PREDICATE_ENDS_WITH_DOUBLE_QUOTE ACTION_PREDICATE_ENDS_WITH_COMMA_OR_DOUBLE_QUOTE
%x COMMENT
%x TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_QUOTE TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_SPACE
%x EXPECTING_VAR_PARAMETER EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED
%x EXPECTING_PARAMETER_ENDS_WITH_QUOTE EXPECTING_PARAMETER_ENDS_WITH_SPACE
%x EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE EXPECTING_ACTIONS_ONLY_ONE
%x TRANSACTION_FROM_OPERATOR_TO_ACTIONS
%x TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS
%x TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS
%x NO_OP_INFORMED_ENDS_WITH_SPACE NO_OP_INFORMED_ENDS_WITH_QUOTE
%x FINISH_ACTIONS
%x LEXING_ERROR
%x LEXING_ERROR_ACTION
%x LEXING_ERROR_VARIABLE
%x SETVAR_ACTION_NONQUOTED
%x SETVAR_ACTION_NONQUOTED_WAITING_COLLECTION_ELEM
%x SETVAR_ACTION_NONQUOTED_WAITING_OPERATION
%x SETVAR_ACTION_NONQUOTED_WAITING_CONTENT
%x SETVAR_ACTION_QUOTED
%x SETVAR_ACTION_QUOTED_WAITING_COLLECTION_ELEM
%x SETVAR_ACTION_QUOTED_WAITING_OPERATION
%x SETVAR_ACTION_QUOTED_WAITING_CONTENT

%{
  // Code run each time a pattern is matched.
  # define YY_USER_ACTION  driver.loc.back()->columns (yyleng);

%}

%%

%{
  // Code run each time yylex is called.
  driver.loc.back()->step();
%}
<EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE,EXPECTING_ACTIONS_ONLY_ONE>{
{ACTION_APPEND}                                                         { return p::make_ACTION_APPEND(yytext, *driver.loc.back()); }
{ACTION_BLOCK}                                                          { return p::make_ACTION_BLOCK(yytext, *driver.loc.back()); }
{ACTION_CAPTURE}                                                        { return p::make_ACTION_CAPTURE(yytext, *driver.loc.back()); }
{ACTION_CHAIN}                                                          { return p::make_ACTION_CHAIN(yytext, *driver.loc.back()); }
{ACTION_DENY}                                                           { return p::make_ACTION_DENY(yytext, *driver.loc.back()); }
{ACTION_DEPRECATE_VAR}                                                  { return p::make_ACTION_DEPRECATE_VAR(yytext, *driver.loc.back()); }
{ACTION_DROP}                                                           { return p::make_ACTION_DROP(yytext, *driver.loc.back()); }
{ACTION_ID}                                                             { return p::make_ACTION_ID(yytext, *driver.loc.back()); }
{ACTION_LOG}                                                            { return p::make_ACTION_LOG(yytext, *driver.loc.back()); }
{ACTION_MULTI_MATCH}                                                    { return p::make_ACTION_MULTI_MATCH(yytext, *driver.loc.back()); }
{ACTION_NO_AUDIT_LOG}                                                   { return p::make_ACTION_NO_AUDIT_LOG(yytext, *driver.loc.back()); }
{ACTION_NO_LOG}                                                         { return p::make_ACTION_NO_LOG(yytext, *driver.loc.back()); }
{ACTION_PASS}                                                           { return p::make_ACTION_PASS(yytext, *driver.loc.back()); }
{ACTION_PAUSE}                                                          { return p::make_ACTION_PAUSE(yytext, *driver.loc.back()); }
{ACTION_PREPEND}                                                        { return p::make_ACTION_PREPEND(yytext, *driver.loc.back()); }
{ACTION_PROXY}                                                          { return p::make_ACTION_PROXY(yytext, *driver.loc.back()); }
{ACTION_SANITISE_ARG}                                                   { return p::make_ACTION_SANITISE_ARG(yytext, *driver.loc.back()); }
{ACTION_SANITISE_MATCHED}                                               { return p::make_ACTION_SANITISE_MATCHED(yytext, *driver.loc.back()); }
{ACTION_SANITISE_MATCHED_BYTES}                                         { return p::make_ACTION_SANITISE_MATCHED_BYTES(yytext, *driver.loc.back()); }
{ACTION_SANITISE_REQUEST_HEADER}                                        { return p::make_ACTION_SANITISE_REQUEST_HEADER(yytext, *driver.loc.back()); }
{ACTION_SANITISE_RESPONSE_HEADER}                                       { return p::make_ACTION_SANITISE_RESPONSE_HEADER(yytext, *driver.loc.back()); }
{ACTION_SETRSC}:                                                        { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_SETRSC(yytext, *driver.loc.back()); }

{ACTION_STATUS}                                                         { return p::make_ACTION_STATUS(yytext, *driver.loc.back()); }
{ACTION_ACCURACY}:'{FREE_TEXT_QUOTE}'                                   { return p::make_ACTION_ACCURACY(yytext, *driver.loc.back()); }
{ACTION_ACCURACY}:{FREE_TEXT_QUOTE}                                     { return p::make_ACTION_ACCURACY(yytext, *driver.loc.back()); }
{ACTION_ALLOW}                                                          { return p::make_ACTION_ALLOW(yytext, *driver.loc.back()); }
{ACTION_AUDIT_LOG}                                                      { return p::make_ACTION_AUDIT_LOG(yytext, *driver.loc.back()); }
{ACTION_CTL_AUDIT_ENGINE}=                                              { return p::make_ACTION_CTL_AUDIT_ENGINE(yytext, *driver.loc.back()); }
{ACTION_CTL_AUDIT_LOG_PARTS}=[+|-]{AUDIT_PARTS}                         { return p::make_ACTION_CTL_AUDIT_LOG_PARTS(yytext, *driver.loc.back()); }
{ACTION_CTL_BDY_JSON}                                                   { return p::make_ACTION_CTL_BDY_JSON(yytext, *driver.loc.back()); }
{ACTION_CTL_BDY_XML}                                                    { return p::make_ACTION_CTL_BDY_XML(yytext, *driver.loc.back()); }
{ACTION_CTL_BDY_URLENCODED}                                             { return p::make_ACTION_CTL_BDY_URLENCODED(yytext, *driver.loc.back()); }
{ACTION_CTL_FORCE_REQ_BODY_VAR}=                                        { return p::make_ACTION_CTL_FORCE_REQ_BODY_VAR(yytext, *driver.loc.back()); }
{ACTION_CTL_PARSE_XML_INTO_ARGS}=                                       { return p::make_ACTION_CTL_PARSE_XML_INTO_ARGS(yytext, *driver.loc.back()); }
{ACTION_CTL_REQUEST_BODY_ACCESS}=                                       { return p::make_ACTION_CTL_REQUEST_BODY_ACCESS(yytext, *driver.loc.back()); }
{ACTION_CTL_RULE_ENGINE}=                                               { return p::make_ACTION_CTL_RULE_ENGINE(*driver.loc.back()); }
{ACTION_CTL_RULE_REMOVE_BY_ID}[=]{REMOVE_RULE_BY}                       { return p::make_ACTION_CTL_RULE_REMOVE_BY_ID(yytext, *driver.loc.back()); }
{ACTION_CTL_RULE_REMOVE_BY_TAG}[=]{REMOVE_RULE_BY}                      { return p::make_ACTION_CTL_RULE_REMOVE_BY_TAG(yytext, *driver.loc.back()); }
{ACTION_CTL_RULE_REMOVE_TARGET_BY_ID}[=]{REMOVE_RULE_BY}                { return p::make_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID(yytext, *driver.loc.back()); }
{ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG}[=]{REMOVE_RULE_BY}               { return p::make_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG(yytext, *driver.loc.back()); }
{ACTION_EXEC}:'{VAR_FREE_TEXT_QUOTE}'                                   { return p::make_ACTION_EXEC(yytext, *driver.loc.back()); }
{ACTION_EXEC}:{VAR_FREE_TEXT_SPACE_COMMA}                               { return p::make_ACTION_EXEC(yytext, *driver.loc.back()); }
{ACTION_EXPIRE_VAR}:                                                    { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_EXPIRE_VAR(yytext, *driver.loc.back()); }
{ACTION_INITCOL}:{COL_NAME}=                                            { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_INITCOL(yytext, *driver.loc.back()); }
{ACTION_MATURITY}:'{FREE_TEXT_QUOTE}'                                   { return p::make_ACTION_MATURITY(yytext, *driver.loc.back()); }
{ACTION_MATURITY}:{FREE_TEXT_QUOTE}                                     { return p::make_ACTION_MATURITY(yytext, *driver.loc.back()); }
{ACTION_MSG}:                                                           { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_MSG(yytext, *driver.loc.back()); }
{ACTION_PHASE}                                                          { return p::make_ACTION_PHASE(yytext, *driver.loc.back()); }
{ACTION_REDIRECT}:                                                      { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_REDIRECT(yytext, *driver.loc.back()); }
{ACTION_REV}:'{FREE_TEXT_QUOTE_COMMA}'                                  { return p::make_ACTION_REV(yytext, *driver.loc.back()); }
{ACTION_REV}:{FREE_TEXT_QUOTE_COMMA}                                    { return p::make_ACTION_REV(yytext, *driver.loc.back()); }
{ACTION_SETENV}:                                                         { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_SETENV(yytext, *driver.loc.back()); }
{ACTION_SETSID}:                                                        { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_SETSID(yytext, *driver.loc.back()); }
{ACTION_SETUID}:                                                        { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_SETUID(yytext, *driver.loc.back()); }

{ACTION_SETVAR}:'                                                       { BEGIN(SETVAR_ACTION_QUOTED); return p::make_ACTION_SETVAR(*driver.loc.back()); }
{ACTION_SETVAR}:                                                        { BEGIN(SETVAR_ACTION_NONQUOTED); return p::make_ACTION_SETVAR(*driver.loc.back()); }


{ACTION_SEVERITY}:'{ACTION_SEVERITY_VALUE}'                             { return p::make_ACTION_SEVERITY(yytext, *driver.loc.back()); }
{ACTION_SEVERITY}:{ACTION_SEVERITY_VALUE}                               { return p::make_ACTION_SEVERITY(yytext, *driver.loc.back()); }
{ACTION_SKIP_AFTER}:{FREE_TEXT_SPACE_COMMA_QUOTE}                       { return p::make_ACTION_SKIP_AFTER(yytext, *driver.loc.back()); }
{ACTION_SKIP}:{CONFIG_VALUE_NUMBER}                                     { return p::make_ACTION_SKIP(yytext, *driver.loc.back()); }
{ACTION_TAG}:                                                           { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_TAG(yytext, *driver.loc.back()); }
{ACTION_VER}:'{FREE_TEXT_QUOTE}'                                        { return p::make_ACTION_VER(yytext, *driver.loc.back()); }
{ACTION_XMLNS}:{FREE_TEXT_SPACE_COMMA_QUOTE}                            { return p::make_ACTION_XMLNS(yytext, *driver.loc.back()); }

{ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT}                               { return p::make_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_PARITY_ODD_7_BIT}                                { return p::make_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT}                               { return p::make_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_SQL_HEX_DECODE}                                  { return p::make_ACTION_TRANSFORMATION_SQL_HEX_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_BASE_64_ENCODE}                                  { return p::make_ACTION_TRANSFORMATION_BASE_64_ENCODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_BASE_64_DECODE}                                  { return p::make_ACTION_TRANSFORMATION_BASE_64_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_BASE_64_DECODE_EXT}                              { return p::make_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_CMD_LINE}                                        { return p::make_ACTION_TRANSFORMATION_CMD_LINE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_SHA1}                                            { return p::make_ACTION_TRANSFORMATION_SHA1(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_MD5}                                             { return p::make_ACTION_TRANSFORMATION_MD5(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE}                               { return p::make_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_HEX_ENCODE}                                      { return p::make_ACTION_TRANSFORMATION_HEX_ENCODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_HEX_DECODE}                                      { return p::make_ACTION_TRANSFORMATION_HEX_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_LOWERCASE}                                       { return p::make_ACTION_TRANSFORMATION_LOWERCASE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_UPPERCASE}                                       { return p::make_ACTION_TRANSFORMATION_UPPERCASE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_URL_ENCODE}                                      { return p::make_ACTION_TRANSFORMATION_URL_ENCODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_URL_DECODE_UNI}                                  { return p::make_ACTION_TRANSFORMATION_URL_DECODE_UNI(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_URL_DECODE}                                      { return p::make_ACTION_TRANSFORMATION_URL_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_NONE}                                            { return p::make_ACTION_TRANSFORMATION_NONE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_COMPRESS_WHITESPACE}                             { return p::make_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REMOVE_WHITESPACE}                               { return p::make_ACTION_TRANSFORMATION_REMOVE_WHITESPACE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REPLACE_NULLS}                                   { return p::make_ACTION_TRANSFORMATION_REPLACE_NULLS(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REMOVE_NULLS}                                    { return p::make_ACTION_TRANSFORMATION_REMOVE_NULLS(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_HTML_ENTITY_DECODE}                              { return p::make_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_JS_DECODE}                                       { return p::make_ACTION_TRANSFORMATION_JS_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_CSS_DECODE}                                      { return p::make_ACTION_TRANSFORMATION_CSS_DECODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_TRIM}                                            { return p::make_ACTION_TRANSFORMATION_TRIM(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_TRIM_LEFT}                                       { return p::make_ACTION_TRANSFORMATION_TRIM_LEFT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_TRIM_RIGHT}                                      { return p::make_ACTION_TRANSFORMATION_TRIM_RIGHT(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_NORMALISE_PATH_WIN}                              { return p::make_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_NORMALISE_PATH}                                  { return p::make_ACTION_TRANSFORMATION_NORMALISE_PATH(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_LENGTH}                                          { return p::make_ACTION_TRANSFORMATION_LENGTH(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_UTF8_TO_UNICODE}                                 { return p::make_ACTION_TRANSFORMATION_UTF8_TO_UNICODE(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR}                            { return p::make_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REMOVE_COMMENTS}                                 { return p::make_ACTION_TRANSFORMATION_REMOVE_COMMENTS(yytext, *driver.loc.back()); }
{ACTION_TRANSFORMATION_REPLACE_COMMENTS}                                { return p::make_ACTION_TRANSFORMATION_REPLACE_COMMENTS(yytext, *driver.loc.back()); }
{ACTION_LOG_DATA}:                                                      { BEGIN(EXPECTING_ACTION_PREDICATE); return p::make_ACTION_LOG_DATA(yytext, *driver.loc.back()); }

{CONFIG_VALUE_DETC}                                                     { return p::make_CONFIG_VALUE_DETC(yytext, *driver.loc.back()); }
{CONFIG_VALUE_ONLYARGS}                                                 { return p::make_CONFIG_VALUE_ONLYARGS(yytext, *driver.loc.back()); }
{CONFIG_VALUE_OFF}                                                      { return p::make_CONFIG_VALUE_OFF(yytext, *driver.loc.back()); }
{CONFIG_VALUE_ON}                                                       { return p::make_CONFIG_VALUE_ON(yytext, *driver.loc.back()); }
{CONFIG_VALUE_RELEVANT_ONLY}                                            { return p::make_CONFIG_VALUE_RELEVANT_ONLY(yytext, *driver.loc.back()); }
[ \t]*\\\n[ \t]*                                                        { driver.loc.back()->lines(1); driver.loc.back()->step(); }
[ \t]*\\\r\n[ \t]*                                                      { driver.loc.back()->lines(1); driver.loc.back()->step(); }
}

<EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE>{
[ \t]*[,][ \t]*                                                         { return p::make_COMMA(*driver.loc.back()); }
}


<EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE>{
[ \t]*\n                                                                { BEGIN(INITIAL); yyless(yyleng); driver.loc.back()->lines(1); driver.loc.back()->step(); }
[ \t]*\r\n                                                              { BEGIN(INITIAL); yyless(yyleng); driver.loc.back()->lines(1); driver.loc.back()->step(); }
}


<EXPECTING_ACTIONS_ONLY_ONE>{
[ ][ \t]*                                                               { BEGIN(INITIAL); yyless(yyleng); }
[ ]*[ \t]*\n                                                            { BEGIN(INITIAL); yyless(1); }
[ ]*[ \t]*\r\n                                                          { BEGIN(INITIAL); driver.loc.back()->lines(1); driver.loc.back()->step(); }
}


<EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE>{
["][ \t]*                                                               { BEGIN(INITIAL); yyless(yyleng); p::make_NEW_LINE(*driver.loc.back()); }
["][ \t]*\n                                                             { BEGIN(INITIAL); yyless(1); }
["][ \t]*\r\n                                                           { BEGIN(INITIAL); driver.loc.back()->lines(1); driver.loc.back()->step(); }
}


<EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE,EXPECTING_ACTIONS_ONLY_ONE>{
.                                                   { BEGIN(LEXING_ERROR_ACTION); yyless(0); }
}


<EXPECTING_ACTION_PREDICATE>{
[']                                                 { BEGIN(ACTION_PREDICATE_ENDS_WITH_QUOTE); }
["]                                                 { BEGIN(ACTION_PREDICATE_ENDS_WITH_DOUBLE_QUOTE); }
.                                                   { BEGIN(ACTION_PREDICATE_ENDS_WITH_COMMA_OR_DOUBLE_QUOTE); yyless(0); }
}


<EXPECTING_ACTION_PREDICATE_VARIABLE,ACTION_PREDICATE_ENDS_WITH_QUOTE,ACTION_PREDICATE_ENDS_WITH_DOUBLE_QUOTE,ACTION_PREDICATE_ENDS_WITH_COMMA_OR_DOUBLE_QUOTE,EXPECTING_PARAMETER_ENDS_WITH_QUOTE,EXPECTING_PARAMETER_ENDS_WITH_SPACE>{
[ \t]*\\\n[ \t]*                                    { driver.loc.back()->lines(1); driver.loc.back()->step(); }
[ \t]*\\\r\n[ \t]*                                  { driver.loc.back()->lines(1); driver.loc.back()->step(); }
}

<EXPECTING_ACTION_PREDICATE_VARIABLE>{
[}][%][{] { yyless(1); BEGIN_PREVIOUS(); }
[}][%]    { BEGIN_PREVIOUS(); }
[}]       { BEGIN_PREVIOUS(); }
}

<ACTION_PREDICATE_ENDS_WITH_QUOTE>{
[']                                                  { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); yyless(yyleng); }
{FREE_TEXT_QUOTE_MACRO_EXPANSION}                    { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<ACTION_PREDICATE_ENDS_WITH_DOUBLE_QUOTE>{
["]                                                  { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); yyless(yyleng); }
{FREE_TEXT_DOUBLE_QUOTE_MACRO_EXPANSION}             { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<ACTION_PREDICATE_ENDS_WITH_COMMA_OR_DOUBLE_QUOTE>{
[,]                                                  { yyless(0); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
["]                                                  { yyless(0); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE);}
{FREE_TEXT_COMMA_DOUBLE_QUOTE_MACRO_EXPANSION}       { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<ACTION_PREDICATE_ENDS_WITH_QUOTE,ACTION_PREDICATE_ENDS_WITH_DOUBLE_QUOTE,ACTION_PREDICATE_ENDS_WITH_COMMA_OR_DOUBLE_QUOTE>{
{START_MACRO_VARIABLE}                               { BEGINX(EXPECTING_ACTION_PREDICATE_VARIABLE); }
.                                                    { BEGIN(LEXING_ERROR_VARIABLE); yyless(0); }
}

<SETVAR_ACTION_NONQUOTED,SETVAR_ACTION_QUOTED>{
{NOT}                                                { return p::make_NOT(*driver.loc.back()); }
.|\n                                                 { BEGIN_ACTION_OPERATION(); yyless(0); }
}


<SETVAR_ACTION_NONQUOTED_WAITING_OPERATION,SETVAR_ACTION_QUOTED_WAITING_OPERATION>{
{EQUALS_PLUS}                                       { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS_PLUS(*driver.loc.back()); }
{EQUALS_MINUS}                                      { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS_MINUS(*driver.loc.back()); }
{EQUALS}                                            { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS(*driver.loc.back()); }
}

<SETVAR_ACTION_NONQUOTED_WAITING_OPERATION>{
.|\n                                                { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); yyless(0);}
}

<SETVAR_ACTION_QUOTED_WAITING_OPERATION>{
\'                                                  { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
.|\n                                                { BEGIN(LEXING_ERROR_ACTION); yyless(0); }
}





<SETVAR_ACTION_NONQUOTED_WAITING_CONTENT,SETVAR_ACTION_QUOTED_WAITING_CONTENT>{
{START_MACRO_VARIABLE}                              { BEGINX(EXPECTING_ACTION_PREDICATE_VARIABLE); }
}


<SETVAR_ACTION_NONQUOTED_WAITING_CONTENT>{
{FREE_TEXT_EQUALS_MACRO_EXPANSION}                  { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
.|\n                                                { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); yyless(0); }
}


<SETVAR_ACTION_QUOTED_WAITING_CONTENT>{
\'                                                  { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
{FREE_TEXT_EQUALS_QUOTE_MACRO_EXPANSION}            { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
.|\n                                                { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); yyless(0); }
}





<FINISH_ACTIONS>{
<<EOF>> { BEGIN(INITIAL); yyless(0); p::make_NEW_LINE(*driver.loc.back()); }
. { BEGIN(INITIAL); }
}

{CONFIG_COMPONENT_SIG}[ \t]+["]{FREE_TEXT}["]                           { return p::make_CONFIG_COMPONENT_SIG(strchr(yytext, ' ') + 2, *driver.loc.back()); }
{CONFIG_SEC_SERVER_SIG}[ \t]+["]{FREE_TEXT}["]                          { return p::make_CONFIG_SEC_SERVER_SIG(strchr(yytext, ' ') + 2, *driver.loc.back()); }
{CONFIG_SEC_WEB_APP_ID}[ \t]+["]{FREE_TEXT}["]                          { return p::make_CONFIG_SEC_WEB_APP_ID(parserSanitizer(strchr(yytext, ' ') + 2), *driver.loc.back()); }
{CONFIG_SEC_WEB_APP_ID}[ \t]+{FREE_TEXT_NEW_LINE}                       { return p::make_CONFIG_SEC_WEB_APP_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_CONTENT_INJECTION}                                              { return p::make_CONFIG_CONTENT_INJECTION(*driver.loc.back()); }
{CONFIG_DIR_AUDIT_DIR_MOD}[ \t]+{CONFIG_VALUE_NUMBER}                   { return p::make_CONFIG_DIR_AUDIT_DIR_MOD(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_DIR_MOD}[ \t]+["]{CONFIG_VALUE_NUMBER}["]             { return p::make_CONFIG_DIR_AUDIT_DIR_MOD(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_DIR}[ \t]+{CONFIG_VALUE_PATH}                         { return p::make_CONFIG_DIR_AUDIT_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_DIR}[ \t]+["]{CONFIG_VALUE_PATH}["]                   { return p::make_CONFIG_DIR_AUDIT_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_ARGUMENT_SEPARATOR}[ \t]+["]{NEW_LINE_FREE_TEXT}["]         { return p::make_CONFIG_SEC_ARGUMENT_SEPARATOR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_ARGUMENT_SEPARATOR}[ \t]+{NEW_LINE_FREE_TEXT}               { return p::make_CONFIG_SEC_ARGUMENT_SEPARATOR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_ENG}                                                  { return p::make_CONFIG_DIR_AUDIT_ENG(yytext, *driver.loc.back()); }
{CONFIG_DIR_AUDIT_FLE_MOD}[ \t]+{CONFIG_VALUE_NUMBER}                   { return p::make_CONFIG_DIR_AUDIT_FLE_MOD(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG2}[ \t]+{CONFIG_VALUE_PATH}                        { return p::make_CONFIG_DIR_AUDIT_LOG2(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG_P}[ \t]+{AUDIT_PARTS}                             { return p::make_CONFIG_DIR_AUDIT_LOG_P(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG_P}[ \t]+["]{AUDIT_PARTS}["]                       { return p::make_CONFIG_DIR_AUDIT_LOG_P(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG}[ \t]+{CONFIG_VALUE_PATH}                         { return p::make_CONFIG_DIR_AUDIT_LOG(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG_FMT}                                              { return p::make_CONFIG_DIR_AUDIT_LOG_FMT(*driver.loc.back()); }
{JSON}                                                                  { return p::make_JSON(*driver.loc.back()); }
{NATIVE}                                                                { return p::make_NATIVE(*driver.loc.back()); }
{CONFIG_DIR_AUDIT_LOG}[ \t]+["]{CONFIG_VALUE_PATH}["]                   { return p::make_CONFIG_DIR_AUDIT_LOG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_STS}[ \t]+{FREE_TEXT_NEW_LINE}                        { return p::make_CONFIG_DIR_AUDIT_STS(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_STS}[ \t]+["]{NEW_LINE_FREE_TEXT}["]                  { return p::make_CONFIG_DIR_AUDIT_STS(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_PREFIX}[ \t]+{FREE_TEXT_NEW_LINE}                     { return p::make_CONFIG_DIR_AUDIT_PREFIX(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_PREFIX}[ \t]+["]{FREE_TEXT_NEW_LINE}["]               { return p::make_CONFIG_DIR_AUDIT_PREFIX(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_AUDIT_TPE}                                                  { return p::make_CONFIG_DIR_AUDIT_TPE(yytext, *driver.loc.back()); }


{CONFIG_DIR_DEBUG_LOG}[ \t]+{CONFIG_VALUE_PATH}                         { return p::make_CONFIG_DIR_DEBUG_LOG(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_DEBUG_LOG}[ \t]+["]{CONFIG_VALUE_PATH}["]                   { return p::make_CONFIG_DIR_DEBUG_LOG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_DEBUG_LVL}[ \t]+{CONFIG_VALUE_NUMBER}                       { return p::make_CONFIG_DIR_DEBUG_LVL(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_GEO_DB}[ \t]+{FREE_TEXT_NEW_LINE}                           { return p::make_CONFIG_DIR_GEO_DB(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION}[ \t]+{CONFIG_VALUE_NUMBER}      { return p::make_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_PCRE_MATCH_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}                { return p::make_CONFIG_DIR_PCRE_MATCH_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_ARGS_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}                      { return p::make_CONFIG_DIR_ARGS_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}       { return p::make_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}        { return p::make_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }

{CONFIG_DIR_REQ_BODY_LIMIT_ACTION}                                      { return p::make_CONFIG_DIR_REQ_BODY_LIMIT_ACTION(yytext, *driver.loc.back()); }
{CONFIG_DIR_REQ_BODY_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}                  { return p::make_CONFIG_DIR_REQ_BODY_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}         { return p::make_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_REQ_BODY}                                                   { return p::make_CONFIG_DIR_REQ_BODY(yytext, *driver.loc.back()); }
{CONFIG_DIR_RES_BODY_LIMIT_ACTION}                                      { return p::make_CONFIG_DIR_RES_BODY_LIMIT_ACTION(yytext, *driver.loc.back()); }
{CONFIG_DIR_RES_BODY_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}                  { return p::make_CONFIG_DIR_RES_BODY_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_RES_BODY}                                                   { return p::make_CONFIG_DIR_RES_BODY(yytext, *driver.loc.back()); }
{CONFIG_DIR_RULE_ENG}                                                   { return p::make_CONFIG_DIR_RULE_ENG(yytext, *driver.loc.back()); }
{CONFIG_DIR_SEC_MARKER}[ \t]+["]{NEW_LINE_FREE_TEXT}["]                 { return p::make_CONFIG_DIR_SEC_MARKER(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_SEC_MARKER}[ \t]+{NEW_LINE_FREE_TEXT}                       { return p::make_CONFIG_DIR_SEC_MARKER(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_DIR_UNICODE_MAP_FILE}[ \t]+{FREE_TEXT_NEW_LINE}[ ]+{CONFIG_VALUE_NUMBER}                    { return p::make_CONFIG_DIR_UNICODE_MAP_FILE(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_SEC_REMOVE_RULES_BY_ID}[ \t]+{FREE_TEXT_NEW_LINE}               { return p::make_CONFIG_SEC_RULE_REMOVE_BY_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_REMOVE_RULES_BY_MSG}[ \t]+{FREE_TEXT_NEW_LINE}              { return p::make_CONFIG_SEC_RULE_REMOVE_BY_MSG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_REMOVE_RULES_BY_MSG}[ \t]+["]{FREE_TEXT_NEW_LINE}["]        { return p::make_CONFIG_SEC_RULE_REMOVE_BY_MSG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_REMOVE_RULES_BY_TAG}[ \t]+{FREE_TEXT_NEW_LINE}              { return p::make_CONFIG_SEC_RULE_REMOVE_BY_TAG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_REMOVE_RULES_BY_TAG}[ \t]+["]{FREE_TEXT_NEW_LINE}["]        { return p::make_CONFIG_SEC_RULE_REMOVE_BY_TAG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_TAG}[ \t]+["]{FREE_TEXT_NEW_LINE}["]       { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_TAG}[ \t]+{FREE_TEXT_SPACE_COMMA_QUOTE}    { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_MSG}[ \t]+["]{FREE_TEXT_NEW_LINE}["]       { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_MSG}[ \t]+{FREE_TEXT_SPACE_COMMA_QUOTE}    { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_ID}[ \t]+["]{FREE_TEXT_NEW_LINE}["]        { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_TARGET_BY_ID}[ \t]+{FREE_TEXT_SPACE_COMMA_QUOTE}     { state_variable_from = 1; BEGIN(TRANSACTION_TO_VARIABLE); return p::make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_ACTION_BY_ID}[ \t]+["]{FREE_TEXT_NEW_LINE}["]        { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_UPDATE_ACTION_BY_ID}[ \t]+{FREE_TEXT_SPACE_COMMA_QUOTE}     { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_UPDLOAD_KEEP_FILES}                                             { return p::make_CONFIG_UPDLOAD_KEEP_FILES(yytext, *driver.loc.back()); }
{CONFIG_UPDLOAD_SAVE_TMP_FILES}                                         { return p::make_CONFIG_UPDLOAD_SAVE_TMP_FILES(yytext, *driver.loc.back()); }
{CONFIG_UPLOAD_DIR}[ \t]+{CONFIG_VALUE_PATH}                            { return p::make_CONFIG_UPLOAD_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_UPLOAD_DIR}[ \t]+["]{CONFIG_VALUE_PATH}["]                      { return p::make_CONFIG_UPLOAD_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_UPLOAD_FILE_LIMIT}[ \t]+{CONFIG_VALUE_NUMBER}                   { return p::make_CONFIG_UPLOAD_FILE_LIMIT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_UPLOAD_FILE_MODE}[ \t]+{CONFIG_VALUE_NUMBER}                    { return p::make_CONFIG_UPLOAD_FILE_MODE(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_VALUE_ABORT}                                                    { return p::make_CONFIG_VALUE_ABORT(yytext, *driver.loc.back()); }
{CONFIG_VALUE_DETC}                                                     { return p::make_CONFIG_VALUE_DETC(yytext, *driver.loc.back()); }
{CONFIG_VALUE_HTTPS}                                                    { return p::make_CONFIG_VALUE_HTTPS(yytext, *driver.loc.back()); }
{CONFIG_VALUE_ONLYARGS}                                                 { return p::make_CONFIG_VALUE_ONLYARGS(yytext, *driver.loc.back()); }
{CONFIG_VALUE_OFF}                                                      { return p::make_CONFIG_VALUE_OFF(yytext, *driver.loc.back()); }
{CONFIG_VALUE_ON}                                                       { return p::make_CONFIG_VALUE_ON(yytext, *driver.loc.back()); }
{CONFIG_VALUE_PARALLEL}                                                 { return p::make_CONFIG_VALUE_PARALLEL(yytext, *driver.loc.back()); }
{CONFIG_VALUE_PROCESS_PARTIAL}                                          { return p::make_CONFIG_VALUE_PROCESS_PARTIAL(yytext, *driver.loc.back()); }
{CONFIG_VALUE_REJECT}                                                   { return p::make_CONFIG_VALUE_REJECT(yytext, *driver.loc.back()); }
{CONFIG_VALUE_RELEVANT_ONLY}                                            { return p::make_CONFIG_VALUE_RELEVANT_ONLY(yytext, *driver.loc.back()); }
{CONFIG_VALUE_SERIAL}                                                   { return p::make_CONFIG_VALUE_SERIAL(yytext, *driver.loc.back()); }
{CONFIG_VALUE_WARN}                                                     { return p::make_CONFIG_VALUE_WARN(yytext, *driver.loc.back()); }
{CONFIG_XML_EXTERNAL_ENTITY}                                            { return p::make_CONFIG_XML_EXTERNAL_ENTITY(yytext, *driver.loc.back()); }
{CONFIG_XML_PARSE_XML_INTO_ARGS}                                        { return p::make_CONFIG_XML_PARSE_XML_INTO_ARGS(yytext, *driver.loc.back()); }
{CONGIG_DIR_RESPONSE_BODY_MP}[ \t]+{FREE_TEXT_NEW_LINE}                 { return p::make_CONGIG_DIR_RESPONSE_BODY_MP(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONGIG_DIR_RESPONSE_BODY_MP_CLEAR}                                     { return p::make_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR(*driver.loc.back()); }
{CONGIG_DIR_SEC_ARG_SEP}[ \t]+{FREE_TEXT_NEW_LINE}                      { return p::make_CONGIG_DIR_SEC_ARG_SEP(yytext, *driver.loc.back()); }
{CONGIG_DIR_SEC_COOKIE_FORMAT}[ \t]+{CONFIG_VALUE_NUMBER}               { return p::make_CONGIG_DIR_SEC_COOKIE_FORMAT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_SEC_COOKIEV0_SEPARATOR}[ \t]+["]{NEW_LINE_FREE_TEXT}["]         { return p::make_CONFIG_SEC_COOKIEV0_SEPARATOR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_COOKIEV0_SEPARATOR}[ \t]+{NEW_LINE_FREE_TEXT}               { return p::make_CONFIG_SEC_COOKIEV0_SEPARATOR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONGIG_DIR_SEC_DATA_DIR}[ \t]+{CONFIG_VALUE_PATH}                      { return p::make_CONGIG_DIR_SEC_DATA_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONGIG_DIR_SEC_DATA_DIR}[ \t]+["]{CONFIG_VALUE_PATH}["]                { return p::make_CONGIG_DIR_SEC_DATA_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONGIG_DIR_SEC_STATUS_ENGINE}[ \t]+{FREE_TEXT_NEW_LINE}                { return p::make_CONGIG_DIR_SEC_STATUS_ENGINE(yytext, *driver.loc.back()); }
{CONGIG_DIR_SEC_TMP_DIR}[ \t]+{CONFIG_VALUE_PATH}                       { return p::make_CONGIG_DIR_SEC_TMP_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONGIG_DIR_SEC_TMP_DIR}[ \t]+["]{CONFIG_VALUE_PATH}["]                 { return p::make_CONGIG_DIR_SEC_TMP_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{DIRECTIVE_SECRULESCRIPT}[ \t]+{CONFIG_VALUE_PATH}                      { BEGIN(TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS); return p::make_DIRECTIVE_SECRULESCRIPT(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{DIRECTIVE_SECRULESCRIPT}[ \t]+["]{FREE_TEXT_SPACE_COMMA_QUOTE}["]      { BEGIN(TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS); return p::make_DIRECTIVE_SECRULESCRIPT(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_CACHE_TRANSFORMATIONS}{FREE_TEXT_NEW_LINE}                  { return p::make_CONFIG_SEC_CACHE_TRANSFORMATIONS(yytext, *driver.loc.back()); }
{CONFIG_SEC_CHROOT_DIR}[ \t]+{CONFIG_VALUE_PATH}                        { return p::make_CONFIG_SEC_CHROOT_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_CHROOT_DIR}[ \t]+["]{CONFIG_VALUE_PATH}["]                  { return p::make_CONFIG_SEC_CHROOT_DIR(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_CONN_ENGINE}                                                    { return p::make_CONFIG_CONN_ENGINE(yytext, *driver.loc.back()); }
{CONFIG_SEC_HASH_ENGINE}                                                { return p::make_CONFIG_SEC_HASH_ENGINE(yytext, *driver.loc.back()); }
{CONFIG_SEC_HASH_KEY}                                                   { return p::make_CONFIG_SEC_HASH_KEY(yytext, *driver.loc.back()); }
{CONFIG_SEC_HASH_PARAM}                                                 { return p::make_CONFIG_SEC_HASH_PARAM(yytext, *driver.loc.back()); }
{CONFIG_SEC_HASH_METHOD_RX}                                             { return p::make_CONFIG_SEC_HASH_METHOD_RX(yytext, *driver.loc.back()); }
{CONFIG_SEC_HASH_METHOD_PM}                                             { return p::make_CONFIG_SEC_HASH_METHOD_PM(yytext, *driver.loc.back()); }
{CONFIG_DIR_GSB_DB}[ \t]+{CONFIG_VALUE_PATH}                            { return p::make_CONFIG_DIR_GSB_DB(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_DIR_GSB_DB}[ \t]+["]{CONFIG_VALUE_PATH}["]                      { return p::make_CONFIG_DIR_GSB_DB(parserSanitizer(strchr(yytext, ' ') + 1), *driver.loc.back()); }
{CONFIG_SEC_GUARDIAN_LOG}                                               { return p::make_CONFIG_SEC_GUARDIAN_LOG(yytext, *driver.loc.back()); }
{CONFIG_SEC_INTERCEPT_ON_ERROR}                                         { return p::make_CONFIG_SEC_INTERCEPT_ON_ERROR(yytext, *driver.loc.back()); }
{CONFIG_SEC_CONN_R_STATE_LIMIT}{FREE_TEXT_NEW_LINE}                     { return p::make_CONFIG_SEC_CONN_R_STATE_LIMIT(yytext, *driver.loc.back()); }
{CONFIG_SEC_CONN_W_STATE_LIMIT}{FREE_TEXT_NEW_LINE}                     { return p::make_CONFIG_SEC_CONN_W_STATE_LIMIT(yytext, *driver.loc.back()); }
{CONFIG_SEC_SENSOR_ID}{FREE_TEXT_NEW_LINE}                              { return p::make_CONFIG_SEC_SENSOR_ID(yytext, *driver.loc.back()); }
{CONFIG_SEC_RULE_INHERITANCE}                                           { return p::make_CONFIG_SEC_RULE_INHERITANCE(yytext, *driver.loc.back()); }
{CONFIG_SEC_RULE_PERF_TIME}[ \t]+{CONFIG_VALUE_NUMBER}                  { return p::make_CONFIG_SEC_RULE_PERF_TIME(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_SEC_STREAM_IN_BODY_INSPECTION}                                  { return p::make_CONFIG_SEC_STREAM_IN_BODY_INSPECTION(yytext, *driver.loc.back()); }
{CONFIG_SEC_STREAM_OUT_BODY_INSPECTION}                                 { return p::make_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION(yytext, *driver.loc.back()); }
{CONFIG_SEC_DISABLE_BACKEND_COMPRESS}                                   { return p::make_CONFIG_SEC_DISABLE_BACKEND_COMPRESS(yytext, *driver.loc.back()); }

{DIRECTIVE}                                                             { BEGIN(TRANSACTION_TO_VARIABLE); return p::make_DIRECTIVE(yytext, *driver.loc.back()); }
{CONFIG_DIR_SEC_DEFAULT_ACTION}                                         { BEGIN(TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS); return p::make_CONFIG_DIR_SEC_DEFAULT_ACTION(yytext, *driver.loc.back()); }
{CONFIG_DIR_SEC_ACTION}                                                 { BEGIN(TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS); return p::make_CONFIG_DIR_SEC_ACTION(yytext, *driver.loc.back()); }

{CONFIG_SEC_REMOTE_RULES_FAIL_ACTION}                                   { return p::make_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION(yytext, *driver.loc.back()); }
{CONFIG_SEC_COLLECTION_TIMEOUT}[ \t]+{CONFIG_VALUE_NUMBER}              { return p::make_CONFIG_SEC_COLLECTION_TIMEOUT(strchr(yytext, ' ') + 1, *driver.loc.back()); }
{CONFIG_SEC_HTTP_BLKEY}[ \t]+{FREE_TEXT_NEW_LINE}                       { return p::make_CONFIG_SEC_HTTP_BLKEY(strchr(yytext, ' ') + 1, *driver.loc.back()); }
[ \t]*[\n]                                                              { driver.loc.back()->lines(1); driver.loc.back()->step(); }
#[ \t]*SecRule[^\\].*\\[ \t]*[\r\n]*                                    { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(COMMENT); }
#[ \t]*SecAction[^\\].*\\[ \t]*[^\\n]                                   { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(COMMENT);  }
#.*                                                                     { driver.loc.back()->step(); /* comment, just ignore. */ }
\r                                                                      { driver.loc.back()->step(); /* carriage return, just ignore. */}
["]                                                                     { return p::make_QUOTATION_MARK(yytext, *driver.loc.back()); }
[,]                                                                     { return p::make_COMMA(*driver.loc.back()); }

<TRANSACTION_TO_VARIABLE>{
[ \t]*                        { BEGIN(EXPECTING_VARIABLE); }
}

<EXPECTING_VARIABLE>{
[|]                                         { return p::make_PIPE(*driver.loc.back()); }
[,]                                         { return p::make_PIPE(*driver.loc.back()); }
["]                                         { return p::make_QUOTATION_MARK(yytext, *driver.loc.back()); }
{VAR_EXCLUSION}                             { return p::make_VAR_EXCLUSION(*driver.loc.back()); }
{VAR_COUNT}                                 { return p::make_VAR_COUNT(*driver.loc.back()); }
}

<EXPECTING_VARIABLE>{
[ \t]+                                      { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_SPACE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
[ \t]*\"                                    { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_QUOTE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
[ \t]*[\\\n]*[ \t]*                         { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_SPACE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
[ \t]*[\\\n]*[ \t]*\"                       { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_QUOTE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
[ \t]*[\\\r\n]*[ \t]*                       { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_SPACE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
[ \t]*[\\\r\n]*[ \t]*\"                     { if (state_variable_from == 0) { BEGIN(EXPECTING_OPERATOR_ENDS_WITH_QUOTE); } else { state_variable_from = 0; BEGIN(INITIAL);} }
}

<TRANSACTION_FROM_DIRECTIVE_TO_ACTIONS>{
[ \t]* {  }
[ \t]*\"[ \t]*                { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\\\n[ \t]*\"[ \t]*      { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\\\r\n[ \t]*\"[ \t]*    { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
}


<EXPECTING_VARIABLE,EXPECTING_ACTION_PREDICATE_VARIABLE>{
.                                           { BEGIN(LEXING_ERROR_VARIABLE); yyless(0); }
{VARIABLE_ARGS_COMBINED_SIZE}               { return p::make_VARIABLE_ARGS_COMBINED_SIZE(*driver.loc.back()); }
{VARIABLE_ARGS_GET_NAMES}                   { return p::make_VARIABLE_ARGS_GET_NAMES(*driver.loc.back()); }
{VARIABLE_ARGS_GET_NAMES}[:.]               { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS_GET_NAMES(*driver.loc.back()); }
{VARIABLE_ARGS_NAMES}                       { return p::make_VARIABLE_ARGS_NAMES(*driver.loc.back()); }
{VARIABLE_ARGS_NAMES}[:.]                   { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS_NAMES(*driver.loc.back()); }
{VARIABLE_ARGS_POST_NAMES}                  { return p::make_VARIABLE_ARGS_POST_NAMES(*driver.loc.back()); }
{VARIABLE_ARGS_POST_NAMES}[:.]              { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS_POST_NAMES(*driver.loc.back()); }
{VARIABLE_AUTH_TYPE}                        { return p::make_VARIABLE_AUTH_TYPE(*driver.loc.back()); }
{VARIABLE_FILES_COMBINED_SIZE}              { return p::make_VARIABLE_FILES_COMBINED_SIZE(*driver.loc.back()); }
{VARIABLE_FULL_REQUEST_LENGTH}              { return p::make_VARIABLE_FULL_REQUEST_LENGTH(*driver.loc.back()); }
{VARIABLE_FULL_REQUEST}                     { return p::make_VARIABLE_FULL_REQUEST(*driver.loc.back()); }
{VARIABLE_INBOUND_DATA_ERROR}               { return p::make_VARIABLE_INBOUND_DATA_ERROR(*driver.loc.back()); }
{VARIABLE_MATCHED_VAR_NAME}                 { return p::make_VARIABLE_MATCHED_VAR_NAME(*driver.loc.back()); }
{VARIABLE_MATCHED_VAR}                      { return p::make_VARIABLE_MATCHED_VAR(*driver.loc.back()); }
{VARIABLE_MSC_PCRE_ERROR}                   { return p::make_VARIABLE_MSC_PCRE_ERROR(*driver.loc.back()); }
{VARIABLE_MSC_PCRE_LIMITS_EXCEEDED}         { return p::make_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED(*driver.loc.back()); }
{VARIABLE_MULTIPART_BOUNDARY_QUOTED}        { return p::make_VARIABLE_MULTIPART_BOUNDARY_QUOTED(*driver.loc.back()); }
{VARIABLE_MULTIPART_BOUNDARY_WHITESPACE}    { return p::make_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE(*driver.loc.back()); }
{VARIABLE_MULTIPART_CRLF_LF_LINES}          { return p::make_VARIABLE_MULTIPART_CRLF_LF_LINES(*driver.loc.back()); }
{VARIABLE_MULTIPART_DATA_AFTER}             { return p::make_VARIABLE_MULTIPART_DATA_AFTER(*driver.loc.back()); }
{VARIABLE_MULTIPART_DATA_BEFORE}            { return p::make_VARIABLE_MULTIPART_DATA_BEFORE(*driver.loc.back()); }
{VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED}    { return p::make_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED(*driver.loc.back()); }
{VARIABLE_MULTIPART_FILENAME}[:.]           { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_MULTIPART_FILENAME(*driver.loc.back()); }
{VARIABLE_MULTIPART_FILENAME}               { return p::make_VARIABLE_MULTIPART_FILENAME(*driver.loc.back()); }
{VARIABLE_MULTIPART_HEADER_FOLDING}         { return p::make_VARIABLE_MULTIPART_HEADER_FOLDING(*driver.loc.back()); }
{VARIABLE_MULTIPART_HEADER_FOLDING}         { return p::make_VARIABLE_MULTIPART_HEADER_FOLDING(*driver.loc.back()); }
{VARIABLE_MULTIPART_INVALID_HEADER_FOLDING} { return p::make_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING(*driver.loc.back()); }
{VARIABLE_MULTIPART_INVALID_PART}           { return p::make_VARIABLE_MULTIPART_INVALID_PART(*driver.loc.back()); }
{VARIABLE_MULTIPART_INVALID_QUOTING}        { return p::make_VARIABLE_MULTIPART_INVALID_QUOTING(*driver.loc.back()); }
{VARIABLE_MULTIPART_LF_LINE}                { return p::make_VARIABLE_MULTIPART_LF_LINE(*driver.loc.back()); }
{VARIABLE_MULTIPART_MISSING_SEMICOLON}      { return p::make_VARIABLE_MULTIPART_MISSING_SEMICOLON(*driver.loc.back()); }
{VARIABLE_MULTIPART_SEMICOLON_MISSING}      { return p::make_VARIABLE_MULTIPART_SEMICOLON_MISSING(*driver.loc.back()); }
{VARIABLE_MULTIPART_NAME}[:.]               { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_MULTIPART_NAME(*driver.loc.back()); }
{VARIABLE_MULTIPART_NAME}                   { return p::make_VARIABLE_MULTIPART_NAME(*driver.loc.back()); }
{VARIABLE_MULTIPART_STRICT_ERROR}           { return p::make_VARIABLE_MULTIPART_STRICT_ERROR(*driver.loc.back()); }
{VARIABLE_MULTIPART_UNMATCHED_BOUNDARY}     { return p::make_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY(*driver.loc.back()); }
{VARIABLE_OUTBOUND_DATA_ERROR}              { return p::make_VARIABLE_OUTBOUND_DATA_ERROR(*driver.loc.back()); }
{VARIABLE_PATH_INFO}                        { return p::make_VARIABLE_PATH_INFO(*driver.loc.back()); }
{VARIABLE_QUERY_STRING}                     { return p::make_VARIABLE_QUERY_STRING(*driver.loc.back()); }
{VARIABLE_REMOTE_ADDR}                      { return p::make_VARIABLE_REMOTE_ADDR(*driver.loc.back()); }
{VARIABLE_REMOTE_HOST}                      { return p::make_VARIABLE_REMOTE_HOST(*driver.loc.back()); }
{VARIABLE_REMOTE_PORT}                      { return p::make_VARIABLE_REMOTE_PORT(*driver.loc.back()); }
{VARIABLE_REQBODY_ERROR_MSG}                { return p::make_VARIABLE_REQBODY_ERROR_MSG(*driver.loc.back()); }
{VARIABLE_REQBODY_ERROR}                    { return p::make_VARIABLE_REQBODY_ERROR(*driver.loc.back()); }
{VARIABLE_REQBODY_PROCESSOR_ERROR_MSG}      { return p::make_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG(*driver.loc.back()); }
{VARIABLE_REQBODY_PROCESSOR_ERROR}          { return p::make_VARIABLE_REQBODY_PROCESSOR_ERROR(*driver.loc.back()); }
{VARIABLE_REQBODY_PROCESSOR}                { return p::make_VARIABLE_REQBODY_PROCESSOR(*driver.loc.back()); }
{VARIABLE_REQUEST_BASENAME}                 { return p::make_VARIABLE_REQUEST_BASENAME(*driver.loc.back()); }
{VARIABLE_REQUEST_BODY_LENGTH}              { return p::make_VARIABLE_REQUEST_BODY_LENGTH(*driver.loc.back()); }
{VARIABLE_REQUEST_BODY}                     { return p::make_VARIABLE_REQUEST_BODY(*driver.loc.back()); }
{VARIABLE_REQUEST_FILE_NAME}                { return p::make_VARIABLE_REQUEST_FILE_NAME(*driver.loc.back()); }
{VARIABLE_REQUEST_HEADERS_NAMES}            { return p::make_VARIABLE_REQUEST_HEADERS_NAMES(*driver.loc.back()); }
{VARIABLE_REQUEST_HEADERS_NAMES}[:.]        { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_REQUEST_HEADERS_NAMES(*driver.loc.back()); }
{VARIABLE_REQUEST_LINE}                     { return p::make_VARIABLE_REQUEST_LINE(*driver.loc.back()); }
{VARIABLE_REQUEST_METHOD}                   { return p::make_VARIABLE_REQUEST_METHOD(*driver.loc.back()); }
{VARIABLE_REQUEST_PROTOCOL}                 { return p::make_VARIABLE_REQUEST_PROTOCOL(*driver.loc.back()); }
{VARIABLE_REQUEST_URI_RAW}                  { return p::make_VARIABLE_REQUEST_URI_RAW(*driver.loc.back()); }
{VARIABLE_REQUEST_URI}                      { return p::make_VARIABLE_REQUEST_URI(*driver.loc.back()); }
{VARIABLE_RESPONSE_BODY}                    { return p::make_VARIABLE_RESPONSE_BODY(*driver.loc.back()); }
{VARIABLE_RESPONSE_CONTENT_LENGTH}          { return p::make_VARIABLE_RESPONSE_CONTENT_LENGTH(*driver.loc.back()); }
{VARIABLE_RESPONSE_CONTENT_TYPE}            { return p::make_VARIABLE_RESPONSE_CONTENT_TYPE(*driver.loc.back()); }
{VARIABLE_RESPONSE_HEADERS_NAMES}           { return p::make_VARIABLE_RESPONSE_HEADERS_NAMES(*driver.loc.back()); }
{VARIABLE_RESPONSE_HEADERS_NAMES}[:.]       { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_RESPONSE_HEADERS_NAMES(*driver.loc.back()); }
{VARIABLE_RESPONSE_PROTOCOL}                { return p::make_VARIABLE_RESPONSE_PROTOCOL(*driver.loc.back()); }
{VARIABLE_RESPONSE_STATUS}                  { return p::make_VARIABLE_RESPONSE_STATUS(*driver.loc.back()); }
{VARIABLE_SERVER_ADDR}                      { return p::make_VARIABLE_SERVER_ADDR(*driver.loc.back()); }
{VARIABLE_SERVER_NAME}                      { return p::make_VARIABLE_SERVER_NAME(*driver.loc.back()); }
{VARIABLE_SERVER_PORT}                      { return p::make_VARIABLE_SERVER_PORT(*driver.loc.back()); }
{VARIABLE_SESSION_ID}                       { return p::make_VARIABLE_SESSION_ID(*driver.loc.back()); }
{VARIABLE_UNIQUE_ID}                        { return p::make_VARIABLE_UNIQUE_ID(*driver.loc.back()); }
{VARIABLE_URL_ENCODED_ERROR}                { return p::make_VARIABLE_URL_ENCODED_ERROR(*driver.loc.back()); }
{VARIABLE_USER_ID}                          { return p::make_VARIABLE_USER_ID(*driver.loc.back()); }
{VARIABLE_WEB_APP_ID}                       { return p::make_VARIABLE_WEB_APP_ID(*driver.loc.back()); }
{VARIABLE_ARGS}                             { return p::make_VARIABLE_ARGS(*driver.loc.back()); }
{VARIABLE_ARGS}[:.]                         { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS(*driver.loc.back()); }
{VARIABLE_ARGS_GET}                         { return p::make_VARIABLE_ARGS_GET(*driver.loc.back()); }
{VARIABLE_ARGS_GET}[:.]                     { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS_GET(*driver.loc.back()); }
{VARIABLE_ARGS_POST}                        { return p::make_VARIABLE_ARGS_POST(*driver.loc.back()); }
{VARIABLE_ARGS_POST}[:.]                    { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_ARGS_POST(*driver.loc.back()); }
{VARIABLE_FILES_SIZES}                      { return p::make_VARIABLE_FILES_SIZES(*driver.loc.back()); }
{VARIABLE_FILES_SIZES}[:.]                  { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_FILES_SIZES(*driver.loc.back()); }
{VARIABLE_FILES_NAMES}                      { return p::make_VARIABLE_FILES_NAMES(*driver.loc.back()); }
{VARIABLE_FILES_NAMES}[:.]                  { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_FILES_NAMES(*driver.loc.back()); }
{VARIABLE_FILES_TMP_CONTENT}                { return p::make_VARIABLE_FILES_TMP_CONTENT(*driver.loc.back()); }
{VARIABLE_FILES_TMP_CONTENT}[:.]            { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_FILES_TMP_CONTENT(*driver.loc.back()); }
{VARIABLE_MATCHED_VARS_NAMES}               { return p::make_VARIABLE_MATCHED_VARS_NAMES(*driver.loc.back()); }
{VARIABLE_MATCHED_VARS_NAMES}[:.]           { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_MATCHED_VARS_NAMES(*driver.loc.back()); }
{VARIABLE_MATCHED_VARS}                     { return p::make_VARIABLE_MATCHED_VARS(*driver.loc.back()); }
{VARIABLE_MATCHED_VARS}[:.]                 { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_MATCHED_VARS(*driver.loc.back()); }
{VARIABLE_FILES}                            { return p::make_VARIABLE_FILES(*driver.loc.back()); }
{VARIABLE_FILES}[:.]                        { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_FILES(*driver.loc.back()); }
{VARIABLE_REQUEST_COOKIES}                  { return p::make_VARIABLE_REQUEST_COOKIES(*driver.loc.back()); }
{VARIABLE_REQUEST_COOKIES}[:.]              { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_REQUEST_COOKIES(*driver.loc.back()); }
{VARIABLE_REQUEST_HEADERS}                  { return p::make_VARIABLE_REQUEST_HEADERS(*driver.loc.back()); }
{VARIABLE_REQUEST_HEADERS}[:.]              { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_REQUEST_HEADERS(*driver.loc.back()); }
{VARIABLE_RESPONSE_HEADERS}                 { return p::make_VARIABLE_RESPONSE_HEADERS(*driver.loc.back()); }
{VARIABLE_RESPONSE_HEADERS}[:.]             { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_RESPONSE_HEADERS(*driver.loc.back()); }
{VARIABLE_GEO}                              { return p::make_VARIABLE_GEO(*driver.loc.back()); }
{VARIABLE_GEO}[:.]                          { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_GEO(*driver.loc.back()); }
{VARIABLE_REQUEST_COOKIES_NAMES}            { return p::make_VARIABLE_REQUEST_COOKIES_NAMES(*driver.loc.back()); }
{VARIABLE_REQUEST_COOKIES_NAMES}[:.]        { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_REQUEST_COOKIES_NAMES(*driver.loc.back()); }
{VARIABLE_MULTIPART_PART_HEADERS}           { return p::make_VARIABLE_MULTIPART_PART_HEADERS(*driver.loc.back()); }
{VARIABLE_MULTIPART_PART_HEADERS}[:.]       { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_MULTIPART_PART_HEADERS(*driver.loc.back()); }
{VARIABLE_RULE}                             { return p::make_VARIABLE_RULE(*driver.loc.back()); }
{VARIABLE_RULE}[:.]                         { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_RULE(*driver.loc.back()); }
{VARIABLE_FILES_TMP_NAMES}                  { return p::make_VARIABLE_FILES_TMP_NAMES(*driver.loc.back()); }
{VARIABLE_FILES_TMP_NAMES}[:.]              { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_VARIABLE_FILES_TMP_NAMES(*driver.loc.back()); }
{RUN_TIME_VAR_XML}                          { return p::make_RUN_TIME_VAR_XML(*driver.loc.back()); }
{RUN_TIME_VAR_XML}[:.]                      { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_RUN_TIME_VAR_XML(*driver.loc.back()); }
{RUN_TIME_VAR_ENV}                          { return p::make_RUN_TIME_VAR_ENV(*driver.loc.back()); }
{RUN_TIME_VAR_ENV}[:.]                      { BEGINX(EXPECTING_VAR_PARAMETER); return p::make_RUN_TIME_VAR_ENV(*driver.loc.back()); }
{RUN_TIME_VAR_BLD}                          { return p::make_RUN_TIME_VAR_BLD(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_DUR}                          { return p::make_RUN_TIME_VAR_DUR(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_HSV}                          { return p::make_RUN_TIME_VAR_HSV(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_REMOTE_USER}                  { return p::make_RUN_TIME_VAR_REMOTE_USER(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_DAY}                     { return p::make_RUN_TIME_VAR_TIME_DAY(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_EPOCH}                   { return p::make_RUN_TIME_VAR_TIME_EPOCH(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_HOUR}                    { return p::make_RUN_TIME_VAR_TIME_HOUR(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_MIN}                     { return p::make_RUN_TIME_VAR_TIME_MIN(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_MON}                     { return p::make_RUN_TIME_VAR_TIME_MON(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_SEC}                     { return p::make_RUN_TIME_VAR_TIME_SEC(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_YEAR}                    { return p::make_RUN_TIME_VAR_TIME_YEAR(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME}                         { return p::make_RUN_TIME_VAR_TIME(yytext, *driver.loc.back()); }
{RUN_TIME_VAR_TIME_WDAY}                    { return p::make_RUN_TIME_VAR_TIME_WDAY(yytext, *driver.loc.back()); }


{VARIABLE_WEBSERVER_ERROR_LOG}              { driver.error (*driver.loc.back(), "Variable VARIABLE_WEBSERVER_ERROR_LOG is not supported by libModSecurity", ""); throw p::syntax_error(*driver.loc.back(), "");}
{VARIABLE_GLOBAL}                           { return p::make_VARIABLE_GLOBAL(*driver.loc.back()); }
{VARIABLE_IP}                               { return p::make_VARIABLE_IP(*driver.loc.back()); }
{VARIABLE_RESOURCE}                         { return p::make_VARIABLE_RESOURCE(*driver.loc.back()); }
{VARIABLE_SESSION}                          { return p::make_VARIABLE_SESSION(*driver.loc.back()); }
{VARIABLE_STATUS}                           { return p::make_VARIABLE_STATUS(*driver.loc.back()); }
{VARIABLE_STATUS_LINE}                      { return p::make_VARIABLE_STATUS_LINE(*driver.loc.back()); }
{VARIABLE_TX}                               { return p::make_VARIABLE_TX(*driver.loc.back()); }
{VARIABLE_USER}                             { return p::make_VARIABLE_USER(*driver.loc.back()); }
}

<EXPECTING_VARIABLE,EXPECTING_ACTION_PREDICATE_VARIABLE,SETVAR_ACTION_NONQUOTED,SETVAR_ACTION_QUOTED>{
{VARIABLE_GLOBAL}[:.]                       { BEGINX_(); return p::make_VARIABLE_GLOBAL(*driver.loc.back()); }
{VARIABLE_IP}[:.]                           { BEGINX_(); return p::make_VARIABLE_IP(*driver.loc.back()); }
{VARIABLE_RESOURCE}[:.]                     { BEGINX_(); return p::make_VARIABLE_RESOURCE(*driver.loc.back()); }
{VARIABLE_SESSION}[:.]                      { BEGINX_(); return p::make_VARIABLE_SESSION(*driver.loc.back()); }
{VARIABLE_TX}[:.]                           { BEGINX_(); return p::make_VARIABLE_TX(*driver.loc.back()); }
{VARIABLE_USER}[:.]                         { BEGINX_(); return p::make_VARIABLE_USER(*driver.loc.back()); }
}


<EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED,EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED>{
{EQUALS_PLUS}                             { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS_PLUS(*driver.loc.back()); }
{EQUALS_MINUS}                            { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS_MINUS(*driver.loc.back()); }
{EQUALS}                                  { BEGIN_ACTION_WAITING_CONTENT(); return p::make_SETVAR_OPERATION_EQUALS(*driver.loc.back()); }
[\/]{DICT_ELEMENT_NO_PIPE}[\/][ ]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
[\/]{DICT_ELEMENT_NO_PIPE}[\/][|]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_WITH_PIPE}[\/][']    { BEGIN_PREVIOUS(); yyless(yyleng - 0); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_WITH_PIPE}[\/]['][|] { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }
{FREE_TEXT_EQUALS_MACRO_EXPANSION}[']     { yyless(yyleng - 1); BEGIN_PREVIOUS(); return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
{FREE_TEXT_EQUALS_MACRO_EXPANSION}        { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }

[\/]{DICT_ELEMENT_NO_PIPE}[\/][,]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_NO_PIPE}[\/]['][,]   { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }
["]                                       { BEGIN_PREVIOUS(); yyless(0); }
[,]                                       { BEGIN_PREVIOUS(); yyless(0); }
.                                         { BEGINX(LEXING_ERROR_ACTION); yyless(0); }
}


<EXPECTING_VAR_PARAMETER>{
[\/]{DICT_ELEMENT_NO_PIPE}[\/]            { BEGIN_PREVIOUS(); yyless(yyleng); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
[\/]{DICT_ELEMENT_NO_PIPE}[\/][ ]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
[\/]{DICT_ELEMENT_NO_PIPE}[\/][|]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_WITH_PIPE}[\/][']    { BEGIN_PREVIOUS(); yyless(yyleng - 0); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_WITH_PIPE}[\/]['][|] { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }
{DICT_ELEMENT_WITH_EQUALS}                { BEGIN_PREVIOUS(); return p::make_DICT_ELEMENT(yytext, *driver.loc.back()); }

[\/]{DICT_ELEMENT_NO_PIPE}[\/][,]         { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 1, yyleng-2), *driver.loc.back()); }
['][\/]{DICT_ELEMENT_NO_PIPE}[\/]['][,]   { BEGIN_PREVIOUS(); yyless(yyleng - 1); return p::make_DICT_ELEMENT_REGEXP(std::string(yytext, 2, yyleng-4), *driver.loc.back()); }

.                                         { BEGINX(LEXING_ERROR_ACTION); yyless(0); }
["]                                       { return p::make_QUOTATION_MARK(yytext, *driver.loc.back()); }
}



<EXPECTING_OPERATOR_ENDS_WITH_SPACE>{
{OPERATOR_GEOLOOKUP}[ ]                   { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_GEOLOOKUP(*driver.loc.back()); }
{OPERATOR_UNCONDITIONAL_MATCH}[ ]         { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_UNCONDITIONAL_MATCH(*driver.loc.back()); }
{OPERATOR_DETECT_SQLI}[ ]                 { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_DETECT_SQLI(*driver.loc.back()); }
{OPERATOR_DETECT_XSS}[ ]                  { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_DETECT_XSS(*driver.loc.back()); }
{OPERATOR_VALIDATE_URL_ENCODING}[ ]       { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_VALIDATE_URL_ENCODING(*driver.loc.back()); }
{OPERATOR_VALIDATE_UTF8_ENCODING}[ ]      { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_VALIDATE_UTF8_ENCODING(*driver.loc.back()); }
}
<EXPECTING_OPERATOR_ENDS_WITH_QUOTE>{
{OPERATOR_GEOLOOKUP}[ ]*["]               { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_GEOLOOKUP(*driver.loc.back()); }
{OPERATOR_UNCONDITIONAL_MATCH}[ ]*["]     { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_UNCONDITIONAL_MATCH(*driver.loc.back()); }
{OPERATOR_DETECT_SQLI}[ ]*["]             { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_DETECT_SQLI(*driver.loc.back()); }
{OPERATOR_DETECT_XSS}[ ]*["]              { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_DETECT_XSS(*driver.loc.back()); }
{OPERATOR_VALIDATE_URL_ENCODING}[ ]*["]   { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_VALIDATE_URL_ENCODING(*driver.loc.back()); }
{OPERATOR_VALIDATE_UTF8_ENCODING}[ ]*["]  { BEGIN(TRANSACTION_FROM_OPERATOR_TO_ACTIONS); return p::make_OPERATOR_VALIDATE_UTF8_ENCODING(*driver.loc.back()); }
}

<EXPECTING_OPERATOR_ENDS_WITH_SPACE,EXPECTING_OPERATOR_ENDS_WITH_QUOTE>{
{OPERATOR_WITHIN}                       { BEGIN_PARAMETER(); return p::make_OPERATOR_WITHIN(*driver.loc.back()); }
{OPERATOR_CONTAINS_WORD}                { BEGIN_PARAMETER(); return p::make_OPERATOR_CONTAINS_WORD(*driver.loc.back()); }
{OPERATOR_CONTAINS}                     { BEGIN_PARAMETER(); return p::make_OPERATOR_CONTAINS(*driver.loc.back()); }
{OPERATOR_ENDS_WITH}                    { BEGIN_PARAMETER(); return p::make_OPERATOR_ENDS_WITH(*driver.loc.back()); }
{OPERATOR_EQ}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_EQ(*driver.loc.back()); }
{OPERATOR_GE}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_GE(*driver.loc.back()); }
{OPERATOR_GT}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_GT(*driver.loc.back()); }
{OPERATOR_IP_MATCH_FROM_FILE}           { BEGIN_PARAMETER(); return p::make_OPERATOR_IP_MATCH_FROM_FILE(*driver.loc.back()); }
{OPERATOR_IP_MATCH}                     { BEGIN_PARAMETER(); return p::make_OPERATOR_IP_MATCH(*driver.loc.back()); }
{OPERATOR_LE}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_LE(*driver.loc.back()); }
{OPERATOR_LT}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_LT(*driver.loc.back()); }
{OPERATOR_PM_FROM_FILE}                 { BEGIN_PARAMETER(); return p::make_OPERATOR_PM_FROM_FILE(*driver.loc.back()); }
{OPERATOR_PM}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_PM(*driver.loc.back()); }
{OPERATOR_RBL}                          { BEGIN_PARAMETER(); return p::make_OPERATOR_RBL( *driver.loc.back()); }
{OPERATOR_RX}                           { BEGIN_PARAMETER(); return p::make_OPERATOR_RX(*driver.loc.back()); }
{OPERATOR_RX_GLOBAL}                    { BEGIN_PARAMETER(); return p::make_OPERATOR_RX_GLOBAL(*driver.loc.back()); }
{OPERATOR_STR_EQ}                       { BEGIN_PARAMETER(); return p::make_OPERATOR_STR_EQ(*driver.loc.back()); }
{OPERATOR_STR_MATCH}                    { BEGIN_PARAMETER(); return p::make_OPERATOR_STR_MATCH(*driver.loc.back()); }
{OPERATOR_BEGINS_WITH}                  { BEGIN_PARAMETER(); return p::make_OPERATOR_BEGINS_WITH(*driver.loc.back()); }
{OPERATOR_INSPECT_FILE}                 { BEGIN_PARAMETER(); return p::make_OPERATOR_INSPECT_FILE(*driver.loc.back()); }
{OPERATOR_FUZZY_HASH}                   { BEGIN_PARAMETER(); return p::make_OPERATOR_FUZZY_HASH(*driver.loc.back()); }
{OPERATOR_VALIDATE_BYTE_RANGE}          { BEGIN_PARAMETER(); return p::make_OPERATOR_VALIDATE_BYTE_RANGE(*driver.loc.back()); }
{OPERATOR_VALIDATE_DTD}                 { BEGIN_PARAMETER(); return p::make_OPERATOR_VALIDATE_DTD(*driver.loc.back()); }
{OPERATOR_VALIDATE_HASH}                { BEGIN_PARAMETER(); return p::make_OPERATOR_VALIDATE_HASH(*driver.loc.back()); }
{OPERATOR_VALIDATE_SCHEMA}              { BEGIN_PARAMETER(); return p::make_OPERATOR_VALIDATE_SCHEMA(*driver.loc.back()); }
{OPERATOR_VERIFY_CC}                    { BEGIN_PARAMETER(); return p::make_OPERATOR_VERIFY_CC(*driver.loc.back()); }
{OPERATOR_VERIFY_CPF}                   { BEGIN_PARAMETER(); return p::make_OPERATOR_VERIFY_CPF(*driver.loc.back()); }
{OPERATOR_VERIFY_SSN}                   { BEGIN_PARAMETER(); return p::make_OPERATOR_VERIFY_SSN(*driver.loc.back()); }
{OPERATOR_VERIFY_SVNR}                   { BEGIN_PARAMETER(); return p::make_OPERATOR_VERIFY_SVNR(*driver.loc.back()); }
{OPERATOR_GSB_LOOKUP}                   { BEGIN_PARAMETER(); return p::make_OPERATOR_GSB_LOOKUP(*driver.loc.back()); }
{OPERATOR_RSUB}                         { BEGIN_PARAMETER(); return p::make_OPERATOR_RSUB(*driver.loc.back()); }

{NOT}                                   { return p::make_NOT(*driver.loc.back()); }
.                                       { BEGIN_NO_OP_INFORMED(); yyless(0); }
}


<TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_SPACE>{
[ ]    { BEGIN(EXPECTING_PARAMETER_ENDS_WITH_SPACE); }
}

<TRANSITION_FROM_OP_TO_EXPECTING_PARAMETER_ENDS_WITH_QUOTE>{
[ ]    { BEGIN(EXPECTING_PARAMETER_ENDS_WITH_QUOTE); }
}

<NO_OP_INFORMED_ENDS_WITH_QUOTE>{
["]                                             { BEGIN(TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS); }
{FREE_TEXT_DOUBLE_QUOTE_MACRO_EXPANSION}        { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<NO_OP_INFORMED_ENDS_WITH_SPACE>{
[ ]                                             { BEGIN(TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS); }
{FREE_TEXT_SPACE_MACRO_EXPANSION}               { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}
<NO_OP_INFORMED_ENDS_WITH_QUOTE,NO_OP_INFORMED_ENDS_WITH_SPACE>{
{START_MACRO_VARIABLE}                          { BEGINX(EXPECTING_ACTION_PREDICATE_VARIABLE); }
.                                               { BEGIN(LEXING_ERROR); yyless(0); }
}

<EXPECTING_PARAMETER_ENDS_WITH_QUOTE>{
["]                                             { BEGIN(TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS); }
{FREE_TEXT_DOUBLE_QUOTE_MACRO_EXPANSION}        { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<EXPECTING_PARAMETER_ENDS_WITH_SPACE>{
[ ]                                             { BEGIN(TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS); }
{FREE_TEXT_SPACE_MACRO_EXPANSION}               { return p::make_FREE_TEXT_QUOTE_MACRO_EXPANSION(yytext, *driver.loc.back()); }
}

<EXPECTING_PARAMETER_ENDS_WITH_QUOTE,EXPECTING_PARAMETER_ENDS_WITH_SPACE,EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED,EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED>{
{START_MACRO_VARIABLE}                          { BEGINX(EXPECTING_ACTION_PREDICATE_VARIABLE); }
.                                               { BEGIN(LEXING_ERROR_VARIABLE); yyless(0); }
}


<TRANSACTION_FROM_OPERATOR_TO_ACTIONS,TRANSACTION_FROM_OPERATOR_PARAMETERS_TO_ACTIONS>{
[ ]+                                  { BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }

[ \t]*\\\n[ \t]*\"[ \t]*              { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\n[ \t]*\"[ \t]*                { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\\\n[ \t]*                      { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }
[ \t]*\n[ \t]*                        { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }

[ \t]*\\\r\\\n[ \t]*\"[ \t]*          { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\\\r\n[ \t]*\"[ \t]*            { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\r\\\n[ \t]*\"[ \t]*            { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\r\n[ \t]*\"[ \t]*              { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }

[ \t]*\\\r\\\n[ \t]*                  { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }
[ \t]*\\\r\n[ \t]*                    { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }
[ \t]*\r\\\n[ \t]*                    { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }
[ \t]*\r\n[ \t]*                      { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ONLY_ONE); }

[ \t]*\"[ \t]*                        { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }

[ \t]*\"[ \t]*\\\n[ \t]*\"[ \t]*      { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\"[ \t]*\n[ \t]*\"[ \t]*        { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }

[ \t]*\"[ \t]*\\\r\n[ \t]*\"[ \t]*    { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\"[ \t]*\\\r\\\n[ \t]*\"[ \t]*  { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\"[ \t]*\r\n[ \t]*\"[ \t]*      { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
[ \t]*\"[ \t]*\r\\\n[ \t]*\"[ \t]*    { driver.loc.back()->lines(1); driver.loc.back()->step(); BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }

[ \t]*\"[ \t]*\"[ \t]*                { BEGIN(EXPECTING_ACTIONS_ENDS_WITH_DOUBLE_QUOTE); }
}


<INITIAL,EXPECTING_OPERATOR_ENDS_WITH_SPACE,EXPECTING_OPERATOR_ENDS_WITH_QUOTE,EXPECTING_VAR_PARAMETER_OR_MACRO_QUOTED,EXPECTING_VAR_PARAMETER_OR_MACRO_NONQUOTED>{
[ \t]+                                {  }
[ \t]*\\\n[ \t]*                      { driver.loc.back()->lines(1); driver.loc.back()->step(); }
[ \t]*\\\r\n[ \t]*                    { driver.loc.back()->lines(1); driver.loc.back()->step(); }
}

<COMMENT>{
.*[ \t]*\\\n[ \t]*                    { driver.loc.back()->lines(1); driver.loc.back()->step(); }
.*[ \t]*\\\r\n[ \t]*                  { driver.loc.back()->lines(1); driver.loc.back()->step(); }
.*[^\\]                               { BEGIN(INITIAL); driver.loc.back()->lines(1); driver.loc.back()->step(); }
}



.                                     { BEGIN(LEXING_ERROR); yyless(0); }

<LEXING_ERROR>.+  { driver.error (*driver.loc.back(), "Invalid input: ", yytext); throw p::syntax_error(*driver.loc.back(), ""); }
<LEXING_ERROR_ACTION>.+  { driver.error (*driver.loc.back(), "Expecting an action, got: ", yytext); throw p::syntax_error(*driver.loc.back(), ""); }
<LEXING_ERROR_VARIABLE>.+  { driver.error (*driver.loc.back(), "Expecting a variable, got:  : ", yytext); throw p::syntax_error(*driver.loc.back(), ""); }


<<EOF>> {
    if (yyin) {
        fclose(yyin);
    }

    yypop_buffer_state();
    if (!YY_CURRENT_BUFFER) {
        return p::make_END(*driver.loc.back());
    }

    yy::location *l = driver.loc.back();
    driver.loc.pop_back();
    delete l;
}


{CONFIG_INCLUDE}[ \t]+{CONFIG_VALUE_PATH} {
    std::string err;
    const char *tmpStr = yytext + strlen("include");
    const char *file   = tmpStr + strspn( tmpStr, " \t");
    std::string fi = modsecurity::utils::find_resource(file, *driver.loc.back()->end.filename, &err);
    if (fi.empty() == true) {
        BEGIN(INITIAL);
        driver.error (*driver.loc.back(), "", file + std::string(": Not able to open file. ") + err);
        throw p::syntax_error(*driver.loc.back(), "");
    }
    std::list<std::string> files = modsecurity::utils::expandEnv(fi, 0);
    files.reverse();
    for (auto& s: files) {
        std::string err;
        std::string f = modsecurity::utils::find_resource(s, *driver.loc.back()->end.filename, &err);
        driver.loc.push_back(new yy::location());
        driver.m_filenames.push_back(f);
        driver.loc.back()->begin.filename = driver.loc.back()->end.filename = &(driver.m_filenames.back());
        yyin = fopen(f.c_str(), "r" );
        if (!yyin) {
            BEGIN(INITIAL);
            driver.loc.pop_back();
            driver.error (*driver.loc.back(), "", s + std::string(": Not able to open file. ") + err);
            throw p::syntax_error(*driver.loc.back(), "");
        }
        yypush_buffer_state(yy_create_buffer( yyin, YY_BUF_SIZE ));
    }
}

{CONFIG_INCLUDE}[ \t]+["]{CONFIG_VALUE_PATH}["] {
    std::string err;
    const char *tmpStr = yytext + strlen("include");
    const char *afterWhitespace   = tmpStr + strspn( tmpStr, " \t");
    std::string file(afterWhitespace+1, strlen(afterWhitespace)-2);
    std::string fi = modsecurity::utils::find_resource(file, *driver.loc.back()->end.filename, &err);
    if (fi.empty() == true) {
        BEGIN(INITIAL);
        driver.error (*driver.loc.back(), "", file + std::string(": Not able to open file. ") + err);
        throw p::syntax_error(*driver.loc.back(), "");
    }
    std::list<std::string> files = modsecurity::utils::expandEnv(fi, 0);
    files.reverse();
    for (auto& s: files) {
        std::string f = modsecurity::utils::find_resource(s, *driver.loc.back()->end.filename, &err);
        driver.loc.push_back(new yy::location());
        driver.m_filenames.push_back(f);
        driver.loc.back()->begin.filename = driver.loc.back()->end.filename = &(driver.m_filenames.back());

        yyin = fopen(f.c_str(), "r" );
        if (!yyin) {
            BEGIN(INITIAL);
            driver.loc.pop_back();
            driver.error (*driver.loc.back(), "", s + std::string(": Not able to open file. ") + err);
            throw p::syntax_error(*driver.loc.back(), "");
        }
        yypush_buffer_state(yy_create_buffer( yyin, YY_BUF_SIZE ));
    }
}

{CONFIG_SEC_REMOTE_RULES}[ ][^ ]+[ ][^\n\r ]+ {
    HttpsClient c;
    std::string key;
    std::string url;

    std::vector<std::string> conf = modsecurity::utils::string::split(yytext, ' ');
    if (conf.size() < 2) {
        driver.error (*driver.loc.back(), "", "SecRemoteRules demands a key and a URI");
        throw p::syntax_error(*driver.loc.back(), "");
    }
    key = conf[1];
    url = conf[2];
    c.setKey(key);

    driver.loc.push_back(new yy::location());
    driver.m_filenames.push_back(url);
    driver.loc.back()->begin.filename = driver.loc.back()->end.filename = &(driver.m_filenames.back());
    YY_BUFFER_STATE temp = YY_CURRENT_BUFFER;
    yypush_buffer_state(temp);

    bool ret = c.download(url);

    if (ret == false) {
        BEGIN(INITIAL);
        if (driver.m_remoteRulesActionOnFailed == RulesSet::OnFailedRemoteRulesAction::WarnOnFailedRemoteRulesAction) {
            /** TODO: Implement the server logging mechanism. */
        }
        if (driver.m_remoteRulesActionOnFailed == RulesSet::OnFailedRemoteRulesAction::AbortOnFailedRemoteRulesAction) {
            driver.error (*driver.loc.back(), "", yytext + std::string(" - Failed to download: ") + c.error);
            throw p::syntax_error(*driver.loc.back(), "");
        }
    }

    yy_scan_string(c.content.c_str());
}


%%

namespace modsecurity {

bool Driver::scan_begin () {
    yy_flex_debug = trace_scanning;

    if (buffer.empty() == false) {
        yy_scan_string(buffer.c_str());
        return true;
    }
    return false;
}

void Driver::scan_end () {
    yylex_destroy();
    BEGIN(INITIAL);
}

}

