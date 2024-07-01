/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifdef __cplusplus
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <memory>
#include <stack>
#endif

#include <stdlib.h>
#include <stddef.h>

#ifndef HEADERS_MODSECURITY_TRANSACTION_H_
#define HEADERS_MODSECURITY_TRANSACTION_H_

#ifndef __cplusplus
typedef struct ModSecurity_t ModSecurity;
typedef struct Transaction_t Transaction;
typedef struct Rules_t RulesSet;
#endif

#include "modsecurity/anchored_set_variable.h"
#include "modsecurity/anchored_variable.h"
#include "modsecurity/intervention.h"
#include "modsecurity/collection/collections.h"
#include "modsecurity/variable_value.h"
#include "modsecurity/collection/collection.h"
#include "modsecurity/variable_origin.h"
#include "modsecurity/anchored_set_variable_translation_proxy.h"
#include "modsecurity/audit_log.h"


#ifndef NO_LOGS
#define ms_dbg(b, c) \
  do { \
      if (m_rules && m_rules->m_debugLog && m_rules->m_debugLog->m_debugLevel >= b) { \
          m_rules->debug(b, *m_id.get(), m_uri, c); \
      } \
  } while (0);
#else
#define ms_dbg(b, c) \
  do { } while (0);
#endif

#ifndef NO_LOGS
#define ms_dbg_a(t, b, c) \
  do { \
      if (t && t->m_rules && t->m_rules->m_debugLog && t->m_rules->m_debugLog->m_debugLevel >= b) { \
          t->debug(b, c); \
      } \
  } while (0);
#else
#define ms_dbg_a(t, b, c) \
    do { } while (0);
#endif


#define LOGFY_ADD(a, b) \
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>(a), strlen(a)); \
    if (b == NULL) { \
      yajl_gen_string(g, reinterpret_cast<const unsigned char*>(""), \
          strlen("")); \
    } else { \
      yajl_gen_string(g, reinterpret_cast<const unsigned char*>(b), \
          strlen(b)); \
    }


#define LOGFY_ADD_INT(a, b) \
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>(a), strlen(a)); \
    yajl_gen_number(g, reinterpret_cast<const char*>(b), strlen(b));

#define LOGFY_ADD_NUM(a, b) \
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>(a), strlen(a)); \
    yajl_gen_integer(g, b);

#ifdef __cplusplus

namespace modsecurity {

class ModSecurity;
class Transaction;
class RulesSet;
class RuleMessage;
namespace actions {
class Action;
namespace disruptive {
enum AllowType : int;
}
}
namespace RequestBodyProcessor {
class XML;
class JSON;
class MultipartPartTmpFile;
}
namespace operators {
class Operator;
}


class TransactionAnchoredVariables {
 public:
    explicit TransactionAnchoredVariables(Transaction *t)
        : m_variableRequestHeadersNames(t, "REQUEST_HEADERS_NAMES"),
        m_variableResponseContentType(t, "RESPONSE_CONTENT_TYPE"),
        m_variableResponseHeadersNames(t, "RESPONSE_HEADERS_NAMES"),
        m_variableARGScombinedSize(t, "ARGS_COMBINED_SIZE"),
        m_variableAuthType(t, "AUTH_TYPE"),
        m_variableFilesCombinedSize(t, "FILES_COMBINED_SIZE"),
        m_variableFullRequest(t, "FULL_REQUEST"),
        m_variableFullRequestLength(t, "FULL_REQUEST_LENGTH"),
        m_variableInboundDataError(t, "INBOUND_DATA_ERROR"),
        m_variableMatchedVar(t, "MATCHED_VAR"),
        m_variableMatchedVarName(t, "MATCHED_VAR_NAME"),
        m_variableMscPcreError(t, "MSC_PCRE_ERROR"),
        m_variableMscPcreLimitsExceeded(t, "MSC_PCRE_LIMITS_EXCEEDED"),
        m_variableMultipartBoundaryQuoted(t, "MULTIPART_BOUNDARY_QUOTED"),
        m_variableMultipartBoundaryWhiteSpace(t,
            "MULTIPART_BOUNDARY_WHITESPACE"),
        m_variableMultipartCrlfLFLines(t, "MULTIPART_CRLF_LF_LINES"),
        m_variableMultipartDataAfter(t, "MULTIPART_DATA_AFTER"),
        m_variableMultipartDataBefore(t, "MULTIPART_DATA_BEFORE"),
        m_variableMultipartFileLimitExceeded(t,
            "MULTIPART_FILE_LIMIT_EXCEEDED"),
        m_variableMultipartHeaderFolding(t, "MULTIPART_HEADER_FOLDING"),
        m_variableMultipartInvalidHeaderFolding(t,
            "MULTIPART_INVALID_HEADER_FOLDING"),
        m_variableMultipartInvalidPart(t, "MULTIPART_INVALID_PART"),
        m_variableMultipartInvalidQuoting(t, "MULTIPART_INVALID_QUOTING"),
        m_variableMultipartLFLine(t, "MULTIPART_LF_LINE"),
        m_variableMultipartMissingSemicolon(t, "MULTIPART_MISSING_SEMICOLON"),
        m_variableMultipartStrictError(t, "MULTIPART_STRICT_ERROR"),
        m_variableMultipartUnmatchedBoundary(t,
            "MULTIPART_UNMATCHED_BOUNDARY"),
        m_variableOutboundDataError(t, "OUTBOUND_DATA_ERROR"),
        m_variablePathInfo(t, "PATH_INFO"),
        m_variableQueryString(t, "QUERY_STRING"),
        m_variableRemoteAddr(t, "REMOTE_ADDR"),
        m_variableRemoteHost(t, "REMOTE_HOST"),
        m_variableRemotePort(t, "REMOTE_PORT"),
        m_variableReqbodyError(t, "REQBODY_ERROR"),
        m_variableReqbodyErrorMsg(t, "REQBODY_ERROR_MSG"),
        m_variableReqbodyProcessorError(t, "REQBODY_PROCESSOR_ERROR"),
        m_variableReqbodyProcessorErrorMsg(t, "REQBODY_PROCESSOR_ERROR_MSG"),
        m_variableReqbodyProcessor(t, "REQBODY_PROCESSOR"),
        m_variableRequestBasename(t, "REQUEST_BASENAME"),
        m_variableRequestBody(t, "REQUEST_BODY"),
        m_variableRequestBodyLength(t, "REQUEST_BODY_LENGTH"),
        m_variableRequestFilename(t, "REQUEST_FILENAME"),
        m_variableRequestLine(t, "REQUEST_LINE"),
        m_variableRequestMethod(t, "REQUEST_METHOD"),
        m_variableRequestProtocol(t, "REQUEST_PROTOCOL"),
        m_variableRequestURI(t, "REQUEST_URI"),
        m_variableRequestURIRaw(t, "REQUEST_URI_RAW"),
        m_variableResource(t, "RESOURCE"),
        m_variableResponseBody(t, "RESPONSE_BODY"),
        m_variableResponseContentLength(t, "RESPONSE_CONTENT_LENGTH"),
        m_variableResponseProtocol(t, "RESPONSE_PROTOCOL"),
        m_variableResponseStatus(t, "RESPONSE_STATUS"),
        m_variableServerAddr(t, "SERVER_ADDR"),
        m_variableServerName(t, "SERVER_NAME"),
        m_variableServerPort(t, "SERVER_PORT"),
        m_variableSessionID(t, "SESSIONID"),
        m_variableUniqueID(t, "UNIQUE_ID"),
        m_variableUrlEncodedError(t, "URLENCODED_ERROR"),
        m_variableUserID(t, "USERID"),
        m_variableArgs(t, "ARGS"),
        m_variableArgsGet(t, "ARGS_GET"),
        m_variableArgsPost(t, "ARGS_POST"),
        m_variableFilesSizes(t, "FILES_SIZES"),
        m_variableFilesNames(t, "FILES_NAMES"),
        m_variableFilesTmpContent(t, "FILES_TMP_CONTENT"),
        m_variableMultipartFileName(t, "MULTIPART_FILENAME"),
        m_variableMultipartName(t, "MULTIPART_NAME"),
        m_variableMatchedVarsNames(t, "MATCHED_VARS_NAMES"),
        m_variableMatchedVars(t, "MATCHED_VARS"),
        m_variableFiles(t, "FILES"),
        m_variableRequestCookies(t, "REQUEST_COOKIES"),
        m_variableRequestHeaders(t, "REQUEST_HEADERS"),
        m_variableResponseHeaders(t, "RESPONSE_HEADERS"),
        m_variableGeo(t, "GEO"),
        m_variableRequestCookiesNames(t, "REQUEST_COOKIES_NAMES"),
        m_variableFilesTmpNames(t, "FILES_TMPNAMES"),
        m_variableMultipartPartHeaders(t, "MULTIPART_PART_HEADERS"),
        m_variableOffset(0),
        m_variableArgsNames("ARGS_NAMES", &m_variableArgs),
        m_variableArgsGetNames("ARGS_GET_NAMES", &m_variableArgsGet),
        m_variableArgsPostNames("ARGS_POST_NAMES", &m_variableArgsPost)
        { }

    AnchoredSetVariable m_variableRequestHeadersNames;
    AnchoredVariable m_variableResponseContentType;
    AnchoredSetVariable m_variableResponseHeadersNames;
    AnchoredVariable m_variableARGScombinedSize;
    AnchoredVariable m_variableAuthType;
    AnchoredVariable m_variableFilesCombinedSize;
    AnchoredVariable m_variableFullRequest;
    AnchoredVariable m_variableFullRequestLength;
    AnchoredVariable m_variableInboundDataError;
    AnchoredVariable m_variableMatchedVar;
    AnchoredVariable m_variableMatchedVarName;
    AnchoredVariable m_variableMscPcreError;
    AnchoredVariable m_variableMscPcreLimitsExceeded;
    AnchoredVariable m_variableMultipartBoundaryQuoted;
    AnchoredVariable m_variableMultipartBoundaryWhiteSpace;
    AnchoredVariable m_variableMultipartCrlfLFLines;
    AnchoredVariable m_variableMultipartDataAfter;
    AnchoredVariable m_variableMultipartDataBefore;
    AnchoredVariable m_variableMultipartFileLimitExceeded;
    AnchoredVariable m_variableMultipartHeaderFolding;
    AnchoredVariable m_variableMultipartInvalidHeaderFolding;
    AnchoredVariable m_variableMultipartInvalidPart;
    AnchoredVariable m_variableMultipartInvalidQuoting;
    AnchoredVariable m_variableMultipartLFLine;
    AnchoredVariable m_variableMultipartMissingSemicolon;
    AnchoredVariable m_variableMultipartStrictError;
    AnchoredVariable m_variableMultipartUnmatchedBoundary;
    AnchoredVariable m_variableOutboundDataError;
    AnchoredVariable m_variablePathInfo;
    AnchoredVariable m_variableQueryString;
    AnchoredVariable m_variableRemoteAddr;
    AnchoredVariable m_variableRemoteHost;
    AnchoredVariable m_variableRemotePort;
    AnchoredVariable m_variableReqbodyError;
    AnchoredVariable m_variableReqbodyErrorMsg;
    AnchoredVariable m_variableReqbodyProcessorError;
    AnchoredVariable m_variableReqbodyProcessorErrorMsg;
    AnchoredVariable m_variableReqbodyProcessor;
    AnchoredVariable m_variableRequestBasename;
    AnchoredVariable m_variableRequestBody;
    AnchoredVariable m_variableRequestBodyLength;
    AnchoredVariable m_variableRequestFilename;
    AnchoredVariable m_variableRequestLine;
    AnchoredVariable m_variableRequestMethod;
    AnchoredVariable m_variableRequestProtocol;
    AnchoredVariable m_variableRequestURI;
    AnchoredVariable m_variableRequestURIRaw;
    AnchoredVariable m_variableResource;
    AnchoredVariable m_variableResponseBody;
    AnchoredVariable m_variableResponseContentLength;
    AnchoredVariable m_variableResponseProtocol;
    AnchoredVariable m_variableResponseStatus;
    AnchoredVariable m_variableServerAddr;
    AnchoredVariable m_variableServerName;
    AnchoredVariable m_variableServerPort;
    AnchoredVariable m_variableSessionID;
    AnchoredVariable m_variableUniqueID;
    AnchoredVariable m_variableUrlEncodedError;
    AnchoredVariable m_variableUserID;

    AnchoredSetVariable m_variableArgs;
    AnchoredSetVariable m_variableArgsGet;
    AnchoredSetVariable m_variableArgsPost;
    AnchoredSetVariable m_variableFilesSizes;
    AnchoredSetVariable m_variableFilesNames;
    AnchoredSetVariable m_variableFilesTmpContent;
    AnchoredSetVariable m_variableMultipartFileName;
    AnchoredSetVariable m_variableMultipartName;
    AnchoredSetVariable m_variableMatchedVarsNames;
    AnchoredSetVariable m_variableMatchedVars;
    AnchoredSetVariable m_variableFiles;
    AnchoredSetVariable m_variableRequestCookies;
    AnchoredSetVariable m_variableRequestHeaders;
    AnchoredSetVariable m_variableResponseHeaders;
    AnchoredSetVariable m_variableGeo;
    AnchoredSetVariable m_variableRequestCookiesNames;
    AnchoredSetVariable m_variableFilesTmpNames;
    AnchoredSetVariable m_variableMultipartPartHeaders;

    int m_variableOffset;

    AnchoredSetVariableTranslationProxy m_variableArgsNames;
    AnchoredSetVariableTranslationProxy m_variableArgsGetNames;
    AnchoredSetVariableTranslationProxy m_variableArgsPostNames;
};

class TransactionSecMarkerManagement {
 public:
    bool isInsideAMarker() const {
        if (m_marker) {
            return true;
        }

        return false;
    }

    std::shared_ptr<std::string> getCurrentMarker() const {
        if (m_marker) {
            return m_marker;
        } else {
            throw;
        }
    }

    void removeMarker() {
        m_marker.reset();
    }

    void addMarker(const std::shared_ptr<std::string> &name) {
        m_marker = name;
    }

 private:
    std::shared_ptr<std::string> m_marker;
};

/** @ingroup ModSecurity_CPP_API */
class Transaction : public TransactionAnchoredVariables, public TransactionSecMarkerManagement {
 public:
    Transaction(ModSecurity *transaction, RulesSet *rules, void *logCbData);
    Transaction(ModSecurity *transaction, RulesSet *rules, char *id,
        void *logCbData);
    ~Transaction();

    Transaction ( const Transaction & ) = delete;
    bool operator ==(const Transaction &b) const { return false; };
    Transaction &operator =(const Transaction &b) const = delete;

    /** TODO: Should be an structure that fits an IP address */
    int processConnection(const char *client, int cPort,
        const char *server, int sPort);
    int processURI(const char *uri, const char *protocol,
        const char *http_version);

    /**
     * Types of request body that ModSecurity may give a special treatment
     * for the data.
     */
    enum RequestBodyType {
      /**
       *
       */
      UnknownFormat,
      /**
       *
       */
      MultiPartRequestBody,
      /**
       *
       */
      WWWFormUrlEncoded,
      /**
       *
       */
      JSONRequestBody,
      /**
       *
       */
      XMLRequestBody
    };

    int processRequestHeaders();
    int addRequestHeader(const std::string& key, const std::string& value);
    int addRequestHeader(const unsigned char *key, const unsigned char *value);
    int addRequestHeader(const unsigned char *key, size_t len_key,
        const unsigned char *value, size_t len_value);

    int processRequestBody();
    int appendRequestBody(const unsigned char *body, size_t size);
    int requestBodyFromFile(const char *path);

    int processResponseHeaders(int code, const std::string& proto);
    int addResponseHeader(const std::string& key, const std::string& value);
    int addResponseHeader(const unsigned char *key, const unsigned char *value);
    int addResponseHeader(const unsigned char *key, size_t len_key,
        const unsigned char *value, size_t len_value);

    int processResponseBody();
    int appendResponseBody(const unsigned char *body, size_t size);

    int processLogging();
    int updateStatusCode(int status);

    bool intervention(ModSecurityIntervention *it);

    bool addArgument(const std::string& orig, const std::string& key,
        const std::string& value, size_t offset);
    bool extractArguments(const std::string &orig, const std::string& buf,
        size_t offset);

    const char *getResponseBody() const;
    size_t getResponseBodyLength();
    size_t getRequestBodyLength();

#ifndef NO_LOGS
    void debug(int, const std::string&) const;
#endif
    void serverLog(std::shared_ptr<RuleMessage> rm);

    int getRuleEngineState() const;

    std::string toJSON(int parts);
    std::string toOldAuditLogFormat(int parts, const std::string &trailer);
    std::string toOldAuditLogFormatIndex(const std::string &filename,
        double size, const std::string &md5);

    /**
     * Filled during the class instantiation, this variable can be later
     * used to fill the SecRule variable `duration'. The variable `duration'
     * is dynamic calculated, it is always relative to the value found in
     * m_creationTimeStamp.
     *
     * @note There is space for performance improvement. This value don't
	 *       need to be filled if there is no rule using the variable
	 *       `duration'.
     */
    clock_t m_creationTimeStamp;

    /**
     * Holds the client IP address.
     */
    std::shared_ptr<std::string> m_clientIpAddress;

    /**
     * Holds the HTTP version: 1.2, 2.0, 3.0 and so on....
     */
    std::string m_httpVersion;

    /**
     * Holds the server IP Address
     */
    std::shared_ptr<std::string> m_serverIpAddress;

    /**
     * Holds the raw URI that was requested.
     */
    std::string m_uri;

    /**
     * Holds the URI that was requests (without the query string).
     */
    std::shared_ptr<std::string> m_uri_no_query_string_decoded;

    /**
     * Holds the combined size of all arguments, later used to fill the
     * variable  ARGS_COMBINED_SIZE.
     */
    double m_ARGScombinedSizeDouble;

    /**
     * Client tcp port.
     */
    int m_clientPort;

    /**
     * This variable is set by the action `severity' and later can be
     * consulted via the SecLanguage variable HIGHEST_SEVERITY.
     */
    int m_highestSeverityAction;

    /**
     * Holds the HTTP return code when it is known. If 0 nothing was
	 * set.
     */
    int m_httpCodeReturned;

    /**
     * Holds the server port.
     */
    int m_serverPort;

    /**
     * ModSecurity instance used to start this transaction. Basically used
     * to fill the server log whenever is needed.
     */
    ModSecurity *m_ms;

    /**
     * Holds the type of the request body, in case there is one.
     */
    RequestBodyType m_requestBodyType;

    /**
     * Holds the request body "processor"
     */
    RequestBodyType m_requestBodyProcessor;

    /**
     * Rules object utilized during this specific transaction.
     */
    RulesSet *m_rules;

    /**
     *
     */
    std::list<int > m_ruleRemoveById;
    std::list<std::pair<int, int> > m_ruleRemoveByIdRange;

    /**
     *
     */
    std::list<std::string> m_ruleRemoveByTag;

    /**
     *
     */
    std::list< std::pair<std::string, std::string> > m_ruleRemoveTargetByTag;

    /**
     *
     */
    std::list< std::pair<int, std::string> > m_ruleRemoveTargetById;

    /**
     *
     */
    int m_requestBodyAccess;

    /**
     * The list m_auditLogModifier contains modifications to the `auditlogs'
     * for this specific request, those modifications can happens via the
     * utilization of the action: `ctl:auditLogParts='
     *
     */
    std::list< std::pair<int, std::string> > m_auditLogModifier;

    /**
     * This transaction's most recent action ctl:auditEngine
     *
     */
    audit_log::AuditLog::AuditLogStatus m_ctlAuditEngine;

    /**
     * This variable holds all the messages asked to be save by the utilization
     * of the actions: `log_data' and `msg'. These should be included on the
     * auditlogs.
     */
    std::list<modsecurity::RuleMessage> m_rulesMessages;

    /**
     * Holds the request body, in case of any.
     */
    std::ostringstream m_requestBody;

    /**
     * Holds the response body, in case of any.
     */
    std::ostringstream m_responseBody;

    /**
     * Contains the unique ID of the transaction. Use by the variable
	 * `UNIQUE_ID'. This unique id is also saved as part of the AuditLog.
     */
    std::shared_ptr<std::string> m_id;

    /**
     * Holds the amount of rules that should be skipped. If bigger than 0 the
     * current rule should be skipped and the number needs to be decreased.
     */
    int m_skip_next;

    /**
     * If allow action was utilized, this variable holds the allow type.
     */
    modsecurity::actions::disruptive::AllowType m_allowType;

    /**
     * Holds the decode URI. Notice that m_uri holds the raw version
     * of the URI.
     */
    std::string m_uri_decoded;

    /**
     * Actions (disruptive?) that should be taken by the connector related to
     * that transaction.
     */
    std::vector<ModSecurityIntervention> m_actions;
    ModSecurityIntervention m_it;

    /**
     * Holds the creation time stamp, using std::time.
     *
     * TODO: m_timeStamp and m_creationTimeStamp may be merged into a single
     *       variable.
     */
    time_t m_timeStamp;


    /**
     * Holds all the collections related to that transaction.
     */
    collection::Collections m_collections;

    /**
     * Holds the whatever matched in the operation utilization.
     * That variable will be further used by the capture action.
     *
     */
    std::list<std::string> m_matched;

    RequestBodyProcessor::XML *m_xml;
    RequestBodyProcessor::JSON *m_json;

    int m_secRuleEngine;

    std::string m_variableDuration;
    std::map<std::string, std::string> m_variableEnvs;
    std::string m_variableHighestSeverityAction;
    std::string m_variableRemoteUser;
    std::string m_variableTime;
    std::string m_variableTimeDay;
    std::string m_variableTimeEpoch;
    std::string m_variableTimeHour;
    std::string m_variableTimeMin;
    std::string m_variableTimeSec;
    std::string m_variableTimeWDay;
    std::string m_variableTimeYear;

    std::vector<std::shared_ptr<RequestBodyProcessor::MultipartPartTmpFile>> m_multipartPartTmpFiles;

 private:
    /**
     * Pointer to the callback function that will be called to fill
     * the web server (connector) log.
     */
    void *m_logCbData;
};


#endif

#ifdef __cplusplus
extern "C" {
#endif

/** @ingroup ModSecurity_C_API */
Transaction *msc_new_transaction(ModSecurity *ms,
    RulesSet *rules, void *logCbData);

/** @ingroup ModSecurity_C_API */
Transaction *msc_new_transaction_with_id(ModSecurity *ms,
    RulesSet *rules, char *id, void *logCbData);

/** @ingroup ModSecurity_C_API */
int msc_process_connection(Transaction *transaction,
    const char *client, int cPort, const char *server, int sPort);

/** @ingroup ModSecurity_C_API */
int msc_process_request_headers(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
int msc_add_request_header(Transaction *transaction, const unsigned char *key,
    const unsigned char *value);

/** @ingroup ModSecurity_C_API */
int msc_add_n_request_header(Transaction *transaction,
    const unsigned char *key, size_t len_key, const unsigned char *value,
    size_t len_value);

/** @ingroup ModSecurity_C_API */
int msc_process_request_body(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
int msc_append_request_body(Transaction *transaction,
    const unsigned char *body, size_t size);

/** @ingroup ModSecurity_C_API */
int msc_request_body_from_file(Transaction *transaction, const char *path);

/** @ingroup ModSecurity_C_API */
int msc_process_response_headers(Transaction *transaction, int code,
    const char* protocol);

/** @ingroup ModSecurity_C_API */
int msc_add_response_header(Transaction *transaction,
    const unsigned char *key, const unsigned char *value);

/** @ingroup ModSecurity_C_API */
int msc_add_n_response_header(Transaction *transaction,
    const unsigned char *key, size_t len_key, const unsigned char *value,
    size_t len_value);

/** @ingroup ModSecurity_C_API */
int msc_process_response_body(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
int msc_append_response_body(Transaction *transaction,
    const unsigned char *body, size_t size);

/** @ingroup ModSecurity_C_API */
int msc_process_uri(Transaction *transaction, const char *uri,
    const char *protocol, const char *http_version);

/** @ingroup ModSecurity_C_API */
const char *msc_get_response_body(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
size_t msc_get_response_body_length(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
size_t msc_get_request_body_length(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
void msc_transaction_cleanup(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
int msc_intervention(Transaction *transaction, ModSecurityIntervention *it);

/** @ingroup ModSecurity_C_API */
int msc_process_logging(Transaction *transaction);

/** @ingroup ModSecurity_C_API */
int msc_update_status_code(Transaction *transaction, int status);

#ifdef __cplusplus
}
}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_TRANSACTION_H_
