ace.define(
  "ace/mode/modsecurity_highlight_rules",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text_highlight_rules",
  ],
  function (acequire, exports, module) {
    "use strict";
    var oop = acequire("ace/lib/oop");
    var TextHighlightRules = acequire(
      "ace/mode/text_highlight_rules"
    ).TextHighlightRules;

    var ModSecurityHighlightRules = function () {
      // Define all regex patterns from the JSON object
      this.$rules = {
        start: [
          // Comment line starting with #
          {
            token: "comment.line.hash.ini",
            regex: /^(?:\s)*(#).*$\n?/,
          },
          // SecMarker directive
          {
            token: ["keyword.headers.modsecurity.directive.marker", "text"],
            regex:
              /^\s*(SecMarker)\s+("(?:[\w:\.\-_/]+)"|(?:[\w:\.\-_/]+)|'(?:[\w:\.\-_/]+)')\s*$/,
          },
          // ModSecurity directives
          {
            token: "keyword.headers.modsecurity.directive",
            regex:
              /^\s*(?:SecAction|SecArgumentSeparator|SecAuditEngine|SecAuditLog|SecAuditLog2|SecAuditLogDirMode|SecAuditLogFormat|SecAuditLogFileMode|SecAuditLogParts|SecAuditLogRelevantStatus|SecAuditLogStorageDir|SecAuditLogType|SecCacheTransformations|SecChrootDir|SecCollectionTimeout|SecComponentSignature|SecConnEngine|SecContentInjection|SecCookieFormat|SecCookieV0Separator|SecDataDir|SecDebugLog|SecDebugLogLevel|SecDefaultAction|SecDisableBackendCompression|SecHashEngine|SecHashKey|SecHashParam|SecHashMethodRx|SecHashMethodPm|SecGeoLookupDb|SecGsbLookupDb|SecGuardianLog|SecHttpBlKey|SecInterceptOnError|SecMarker|SecPcreMatchLimit|SecPcreMatchLimitRecursion|SecPdfProtect|SecPdfProtectMethod|SecPdfProtectSecret|SecPdfProtectTimeout|SecPdfProtectTokenName|SecReadStateLimit|SecConnReadStateLimit|SecSensorId|SecWriteStateLimit|SecConnWriteStateLimit|SecRemoteRules|SecRemoteRulesFailAction|SecRequestBodyAccess|SecRequestBodyInMemoryLimit|SecRequestBodyLimit|SecRequestBodyNoFilesLimit|SecRequestBodyLimitAction|SecResponseBodyLimit|SecResponseBodyLimitAction|SecResponseBodyMimeType|SecResponseBodyMimeTypesClear|SecResponseBodyAccess|SecRule|SecRuleInheritance|SecRuleEngine|SecRulePerfTime|SecRuleRemoveById|SecRuleRemoveByMsg|SecRuleRemoveByTag|SecRuleScript|SecRuleUpdateActionById|SecRuleUpdateTargetById|SecRuleUpdateTargetByMsg|SecRuleUpdateTargetByTag|SecServerSignature|SecStatusEngine|SecStreamInBodyInspection|SecStreamOutBodyInspection|SecTmpDir|SecUnicodeMapFile|SecUnicodeCodePage|SecUploadDir|SecUploadFileLimit|SecUploadFileMode|SecUploadKeepFiles|SecWebAppId|SecXmlExternalEntity)\b/i,
          },
          // Common typos
          {
            token: "invalid.illegal.modsecurity",
            regex: /(?:^|\s)(ARGS[:\.]ARGS[:\.]|TX[:\.]TX[:\.])/i,
          },
          // Bare variables
          {
            token: "variable.parameter.modsecurity",
            regex:
              /(?:^|\s)(!?\b(?:XML|WEBSERVER_ERROR_LOG|WEBAPPID|USERAGENT_IP|USERID|URLENCODED_ERROR|UNIQUE_ID|TX|TIME_YEAR|TIME_WDAY|TIME_SEC|TIME_MON|TIME_MIN|TIME_HOUR|TIME_EPOCH|TIME_DAY|TIME|STREAM_OUTPUT_BODY|STREAM_INPUT_BODY|SESSIONID|STATUS_LINE|SESSION|SERVER_PORT|SERVER_NAME|SERVER_ADDR|SDBM_DELETE_ERROR|SCRIPT_USERNAME|SCRIPT_UID|SCRIPT_MODE|SCRIPT_GROUPNAME|SCRIPT_GID|SCRIPT_FILENAME|SCRIPT_BASENAME|RULE|RESPONSE_STATUS|RESPONSE_PROTOCOL|RESPONSE_HEADERS_NAMES|RESPONSE_HEADERS|RESPONSE_CONTENT_TYPE|RESPONSE_CONTENT_LENGTH|RESPONSE_BODY|REQUEST_URI_RAW|REQUEST_URI|REQUEST_PROTOCOL|REQUEST_METHOD|REQUEST_LINE|REQUEST_HEADERS_NAMES|REQUEST_HEADERS|REQUEST_FILENAME|REQUEST_COOKIES_NAMES|REQUEST_COOKIES|REQUEST_BODY_LENGTH|REQUEST_BODY|REQUEST_BASENAME|REQBODY_PROCESSOR|REQBODY_ERROR_MSG|REQBODY_ERROR|REMOTE_USER|REMOTE_PORT|REMOTE_HOST|REMOTE_ADDR|QUERY_STRING|PERF_SWRITE|PERF_SREAD|PERF_RULES|PERF_PHASE5|PERF_PHASE4|PERF_PHASE3|PERF_PHASE2|PERF_PHASE1|PERF_LOGGING|PERF_GC|PERF_COMBINED|PERF_ALL|PATH_INFO|OUTBOUND_DATA_ERROR|MULTIPART_UNMATCHED_BOUNDARY|MULTIPART_STRICT_ERROR|MULTIPART_NAME|MULTIPART_FILENAME|MULTIPART_CRLF_LF_LINES|MODSEC_BUILD|MATCHED_VARS_NAMES|MATCHED_VAR_NAME|MATCHED_VARS|MATCHED_VAR|INBOUND_DATA_ERROR|HIGHEST_SEVERITY|GEO|FILES_TMP_CONTENT|FILES_TMPNAMES|FILES_SIZES|FULL_REQUEST_LENGTH|FULL_REQUEST|FILES_NAMES|FILES_COMBINED_SIZE|FILES|ENV|DURATION|AUTH_TYPE|ARGS_POST_NAMES|ARGS_POST|ARGS_NAMES|ARGS_GET_NAMES|ARGS_GET|ARGS_COMBINED_SIZE|ARGS)(?:[:\.][A-Za-z0-9\/\-\_\[\]\*]+|\b))/i,
          },
          // Macro expanded variables
          {
            token: [
              "keyword.macro.modsecurity",
              "variable.parameter.modsecurity",
              "text",
            ],
            regex: /(%\{)([^\}]*)(\})/,
          },
          // Rule action - runtime configuration (ctl)
          {
            token: [
              "text",
              "keyword.operator.modsecurity.action.ctl",
              "keyword.operator.modsecurity.action.ctl.name",
              "punctuation.equals.modsecurity",
              "constant.numeric.modsecurity.action.ctl.parameter",
            ],
            regex:
              /(^|,|\s)(ctl:)(auditEngine|auditLogParts|debugLogLevel|forceRequestBodyVariable|requestBodyAccess|requestBodyLimit|requestBodyProcessor|responseBodyAccess|responseBodyLimit|ruleEngine|ruleRemoveById|ruleRemoveByMsg|ruleRemoveByTag|ruleRemoveTargetById|ruleRemoveTargetByMsg|ruleRemoveTargetByTag|hashEngine|hashEnforcement)(=)((?:\d+)|(?:[\w\s:\.\-_/+]+))/i,
          },
          // Rule action - transform (t)
          {
            token: [
              "text",
              "keyword.operator.modsecurity.action.transform",
              "constant.numeric.modsecurity.action.transform_name",
            ],
            regex:
              /(^|,|\s)(t):'?(base64DecodeExt|base64Decode|sqlHexDecode|base64Encode|cmdLine|compressWhitespace|cssDecode|escapeSeqDecode|hexDecode|hexEncode|htmlEntityDecode|jsDecode|length|lowercase|md5|none|normalisePathWin|normalisePath|normalizePathWin|normalizePath|parityEven7bit|parityOdd7bit|parityZero7bit|removeNulls|removeWhitespace|replaceComments|removeCommentsChar|removeComments|replaceNulls|urlDecodeUni|urlDecode|uppercase|urlEncode|utf8toUnicode|sha1|trimLeft|trimRight|trim)'?/i,
          },
          // Rule action - phase
          {
            token: [
              "text",
              "keyword.operator.modsecurity.action.phase",
              "punctuation.colon.modsecurity",
              "constant.numeric.modsecurity.action.phase_name",
            ],
            regex: /(^|,|\s)(phase)(:)'?(response|request|1|2|3|4|5)'?/i,
          },
          // Rule action - severity
          {
            token: [
              "text",
              "keyword.operator.modsecurity.action.severity",
              "punctuation.colon.modsecurity",
              "constant.numeric.modsecurity.action.severity_name",
            ],
            regex:
              /(^|,|\s)(severity)(:)'?(NOTICE|WARNING|ERROR|CRITICAL|1|2|3|4|5)'?/i,
          },
          // Rule action - with parameter
          {
            token: [
              "text",
              "keyword.operator.modsecurity.action",
              "punctuation.colon.modsecurity",
            ],
            regex:
              /(^|,|\s)(accuracy|append|deprecatevar|exec|expirevar|id|initcol|logdata|maturity|msg|pause|prepend|rev|sanitiseArg|sanitiseMatched|sanitiseMatchedBytes|sanitiseRequestHeader|sanitiseResponseHeader|setuid|setrsc|setsid|setenv|setvar|skip|skipAfter|status|tag|ver|xmlns)(:)(?:'?(?:\d+)'?|(?:\d+)|'(?:[\w\s:\.\-_/(),]+)'|[\w\s:\.\-_/(),]+)/i,
          },
          // Rule action - without parameters
          {
            token: "keyword.operator.modsecurity.action",
            regex:
              /(^|,|\s)(auditlog|capture|log|multiMatch|noauditlog|nolog)\b/i,
          },
          // Rule action - disruptive actions without parameters
          {
            token: "entity.name.function.modsecurity.action.disruptive_pass",
            regex: /(^|,|\s)(allow|block|deny|drop|pass|chain)\b/i,
          },
          // Regexp operator and operand, e.g., "@rx foo"
          {
            token: ["keyword.control.modsecurity", "string.regexp.modsecurity"],
            regex: /"(!?@rx)\s+((?:[^"\\]|\\.)*)"/i,
          },
          // pm operator and operand, e.g., "@pm foo"
          {
            token: [
              "keyword.control.modsecurity",
              "string.unquoted.modsecurity",
            ],
            regex: /"(!?@pm)\s+((?:[^"\\]|\\.)*)"/i,
          },
          // Operator, e.g., @contains
          {
            token: "keyword.control.modsecurity",
            regex:
              /@(?:beginsWith|contains|containsWord|detectSQLi|detectXSS|endsWith|fuzzyHash|eq|ge|geoLookup|gsbLookup|gt|inspectFile|ipMatch|ipMatchF|ipMatchFromFile|le|lt|noMatch|pmf|pmFromFile|rbl|rsub|streq|strmatch|unconditionalMatch|validateByteRange|validateDTD|validateHash|validateSchema|validateUrlEncoding|validateUtf8Encoding|verifyCC|verifyCPF|verifySSN|within)\b/i,
          },
          // Implicit regexp operator by double-quoted string
          {
            token: "string.regexp.modsecurity",
            regex: /"([^@](?:[^"\\]|\\.)*)"/i,
          },
          // IP address/network
          {
            token: "constant.other.modsecurity.ip",
            regex: /\b\d+\.\d+\.\d+\.\d+(?:\/\d+)?\b/,
          },
          // Numbers, e.g., rule IDs
          {
            token: "constant.numeric.modsecurity",
            regex: /\b\d+(\.\d+)?/,
          },
          // Apache configuration directives and tags
          {
            token: [
              "punctuation.definition.tag.apacheconf",
              "entity.tag.apacheconf",
              "text",
              "string.value.apacheconf",
              "punctuation.definition.tag.apacheconf",
            ],
            regex:
              /(<)(Proxy|ProxyMatch|IfVersion|Directory|DirectoryMatch|Files|FilesMatch|IfDefine|IfModule|Limit|LimitExcept|Location|LocationMatch|VirtualHost|Macro|If|Else|ElseIf)(\s(.+?))?(>)/,
          },
          {
            token: [
              "punctuation.definition.tag.apacheconf",
              "entity.tag.apacheconf",
              "punctuation.definition.tag.apacheconf",
            ],
            regex:
              /(<\/)(Proxy|ProxyMatch|IfVersion|Directory|DirectoryMatch|Files|FilesMatch|IfDefine|IfModule|Limit|LimitExcept|Location|LocationMatch|VirtualHost|Macro|If|Else|ElseIf)(>)/,
          },
          // Additional Apache configuration directives
          // ... (You can include more rules here as per your JSON patterns)
        ],
      };

      // Normalize the rules to ensure proper functionality
      this.normalizeRules();
    };

    oop.inherits(ModSecurityHighlightRules, TextHighlightRules);

    exports.ModSecurityHighlightRules = ModSecurityHighlightRules;
  }
);

ace.define(
  "ace/mode/modsecurity",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text",
    "ace/mode/modsecurity_highlight_rules",
  ],
  function (acequire, exports, module) {
    "use strict";
    var oop = acequire("ace/lib/oop");
    var TextMode = acequire("ace/mode/text").Mode;

    var ModSecurityHighlightRules = acequire(
      "ace/mode/modsecurity_highlight_rules"
    ).ModSecurityHighlightRules;

    var Mode = function () {
      this.HighlightRules = ModSecurityHighlightRules;
      this.lineCommentStart = "#";
    };
    oop.inherits(Mode, TextMode);

    (function () {
      this.$id = "ace/mode/modsecurity";
    }).call(Mode.prototype);

    exports.Mode = Mode;
  }
);
