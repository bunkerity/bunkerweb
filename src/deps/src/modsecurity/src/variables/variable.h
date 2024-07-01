/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <exception>
#include <list>
#include <memory>
#include <string>
#include <utility>
#include <vector>
#include <deque>

#include "modsecurity/rules_set.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "src/utils/string.h"
#include "src/utils/regex.h"

#ifndef SRC_VARIABLES_VARIABLE_H_
#define SRC_VARIABLES_VARIABLE_H_

#define DEFINE_VARIABLE(n, N, e) \
    VAR_DIRECT(n, N, e)

#define DEFINE_VARIABLE_DICT(n, N, e) \
    VAR_WITH_DICT_ELEMENT(n, N, e) \
    \
    VAR_WITHOUT_DICT_ELEMENT(n, N, e) \
    \
    VAR_WITH_REGEX(n, N, e) \



#define VAR_WITH_REGEX(n, N, e) \
class n ## _DictElementRegexp : public VariableRegex { \
 public: \
    explicit n ## _DictElementRegexp(const std::string &regex) \
        : VariableRegex(#N, regex) { } \
\
    void evaluate(Transaction *transaction, \
        RuleWithActions *rule, \
        std::vector<const VariableValue *> *l) override { \
        transaction-> e .resolveRegularExpression(&m_r, l, \
            m_keyExclusion); \
    } \
};


#define VAR_WITH_DICT_ELEMENT(n, N, e) \
class n ## _DictElement : public VariableDictElement { \
 public: \
    explicit n ## _DictElement(const std::string &dictElement) \
        : VariableDictElement(#N, dictElement) { } \
\
    void evaluate(Transaction *transaction, \
        RuleWithActions *rule, \
        std::vector<const VariableValue *> *l) override { \
        transaction-> e .resolve(m_dictElement, l); \
    } \
};


#define VAR_WITHOUT_DICT_ELEMENT(n, N, e) \
class n ## _NoDictElement : public Variable { \
 public: \
    explicit n ## _NoDictElement() \
        : Variable(#N) { } \
\
    void evaluate(Transaction *transaction, \
        RuleWithActions *rule, \
        std::vector<const VariableValue *> *l) override { \
        transaction-> e .resolve(l, m_keyExclusion); \
    } \
};


#define VAR_DIRECT(n, N, e) \
class n : public Variable { \
 public: \
    n() \
        : Variable(#N) { } \
    \
    void evaluate(Transaction *transaction, \
        RuleWithActions *rule, \
        std::vector<const VariableValue *> *l) override { \
        transaction-> e .evaluate(l); \
    } \
};


namespace modsecurity {

class Transaction;
namespace variables {

class KeyExclusion {
 public:
    KeyExclusion() { }
    virtual bool match(const std::string &a) = 0;
    virtual ~KeyExclusion() { }
};


// FIXME: use pre built regex.
class KeyExclusionRegex : public KeyExclusion {
 public:
    explicit KeyExclusionRegex(const Utils::Regex &re)
        : m_re(re.pattern, true) { }
    explicit KeyExclusionRegex(const std::string &re)
        : m_re(re, true) { }

    ~KeyExclusionRegex() override { }

    bool match(const std::string &a) override {
        return m_re.searchAll(a).size() > 0;
    }

    Utils::Regex m_re;
};


class KeyExclusionString : public KeyExclusion {
 public:
    explicit KeyExclusionString(std::string &a)
        : m_key(utils::string::toupper(a)) { }

    ~KeyExclusionString() override { }

    bool match(const std::string &a) override {
        return a.size() == m_key.size() && std::equal(a.begin(), a.end(),
            m_key.begin(),
            [](char aa, char bb) {
                return static_cast<char>(toupper(aa)) == static_cast<char>(bb);
            });
    }

    std::string m_key;
};


class KeyExclusions : public std::deque<std::unique_ptr<KeyExclusion>> {
 public:
    KeyExclusions() {
    }

    bool toOmit(std::string a) {
        for (auto &z : *this) {
            if (z->match(a)) {
                return true;
            }
        }
        return false;
    }
};


class VariableMonkeyResolution {
 public:
    VariableMonkeyResolution () { }
    static inline bool comp(const std::string &a, const std::string &b) {
        return a.size() == b.size()
             && std::equal(a.begin(), a.end(), b.begin(),
            [](char aa, char bb) {
            return toupper(aa) == bb;
        });
    }

    static void stringMatchResolveMulti(Transaction *t,
        const std::string &variable,
        std::vector<const VariableValue *> *l) {
        size_t collection_delimiter_offset = variable.find(".");
        if (collection_delimiter_offset == std::string::npos) {
            collection_delimiter_offset = variable.find(":");
        }
        std::string col; // collection name excluding individual variable specification
        std::string var; // variable within the collection
        if (collection_delimiter_offset == std::string::npos) {
            col = variable;
        } else {
            col = std::string(variable, 0, collection_delimiter_offset);
            var = std::string(variable, collection_delimiter_offset + 1,
                variable.length() - (collection_delimiter_offset + 1));
	}

        // First check if the request is for a collection of type AnchoredSetVariable
        AnchoredSetVariable* anchoredSetVariable = NULL;
        if (comp(col, "ARGS")) {
            anchoredSetVariable = &t->m_variableArgs;
        } else if (comp(col, "ARGS_GET")) {
            anchoredSetVariable = &t->m_variableArgsGet;
        } else if (comp(col, "ARGS_POST")) {
            anchoredSetVariable = &t->m_variableArgsPost;
        } else if (comp(col, "FILES_SIZES")) {
            anchoredSetVariable = &t->m_variableFilesSizes;
        } else if (comp(col, "FILES_NAMES")) {
            anchoredSetVariable = &t->m_variableFilesNames;
        } else if (comp(col, "FILES_TMP_CONTENT")) {
            anchoredSetVariable = &t->m_variableFilesTmpContent;
        } else if (comp(col, "MULTIPART_FILENAME")) {
            anchoredSetVariable = &t->m_variableMultipartFileName;
        } else if (comp(col, "MULTIPART_NAME")) {
            anchoredSetVariable = &t->m_variableMultipartName;
        } else if (comp(col, "MATCHED_VARS_NAMES")) {
            anchoredSetVariable = &t->m_variableMatchedVarsNames;
        } else if (comp(col, "MATCHED_VARS")) {
            anchoredSetVariable = &t->m_variableMatchedVars;
        } else if (comp(col, "FILES")) {
            anchoredSetVariable = &t->m_variableFiles;
        } else if (comp(col, "REQUEST_COOKIES")) {
            anchoredSetVariable = &t->m_variableRequestCookies;
        } else if (comp(col, "REQUEST_HEADERS")) {
            anchoredSetVariable = &t->m_variableRequestHeaders;
        } else if (comp(variable, "REQUEST_HEADERS_NAMES")) {
            anchoredSetVariable = &t->m_variableRequestHeadersNames;
        } else if (comp(col, "RESPONSE_HEADERS")) {
            anchoredSetVariable = &t->m_variableResponseHeaders;
        } else if (comp(variable, "RESPONSE_HEADERS_NAMES")) {
            anchoredSetVariable = &t->m_variableResponseHeadersNames;
        } else if (comp(col, "GEO")) {
            anchoredSetVariable = &t->m_variableGeo;
        } else if (comp(col, "REQUEST_COOKIES_NAMES")) {
            anchoredSetVariable = &t->m_variableRequestCookiesNames;
        } else if (comp(col, "MULTIPART_PART_HEADERS")) {
            anchoredSetVariable = &t->m_variableMultipartPartHeaders;
        } else if (comp(col, "FILES_TMPNAMES")) {
            anchoredSetVariable = &t->m_variableFilesTmpNames;
        }
        if (anchoredSetVariable != NULL) {
            if (collection_delimiter_offset == std::string::npos) {
                anchoredSetVariable->resolve(l);
            } else {
                anchoredSetVariable->resolve(var, l);
            }
            return;
        }

        // Next check for collection of type AnchoredSetVariableTranslationProxy
        AnchoredSetVariableTranslationProxy* anchoredSetVariableTranslationProxy = NULL;
        if (comp(col, "ARGS_NAMES")) {
            anchoredSetVariableTranslationProxy = &t->m_variableArgsNames;
        } else if (comp(col, "ARGS_GET_NAMES")) {
            anchoredSetVariableTranslationProxy = &t->m_variableArgsGetNames;
        } else if (comp(col, "ARGS_POST_NAMES")) {
            anchoredSetVariableTranslationProxy = &t->m_variableArgsPostNames;
        }
        if (anchoredSetVariableTranslationProxy != NULL) {
            if (collection_delimiter_offset == std::string::npos) {
                anchoredSetVariableTranslationProxy->resolve(l);
            } else {
                anchoredSetVariableTranslationProxy->resolve(var, l);
            }
            return;
        }


        // It could still be a non-collection variable, but in that case
        // there should not be a request for a variable-within-a-collection
        if (collection_delimiter_offset != std::string::npos) {
            throw std::invalid_argument("Variable not found.");
        }

        if (comp(variable, "RESPONSE_CONTENT_TYPE")) {
            t->m_variableResponseContentType.evaluate(l);
        } else if (comp(variable, "ARGS_COMBINED_SIZE")) {
            t->m_variableARGScombinedSize.evaluate(l);
        } else if (comp(variable, "AUTH_TYPE")) {
            t->m_variableAuthType.evaluate(l);
        } else if (comp(variable, "FILES_COMBINED_SIZE")) {
            t->m_variableFilesCombinedSize.evaluate(l);
        } else if (comp(variable, "FULL_REQUEST")) {
            t->m_variableFullRequest.evaluate(l);
        } else if (comp(variable, "FULL_REQUEST_LENGTH")) {
            t->m_variableFullRequestLength.evaluate(l);
        } else if (comp(variable, "INBOUND_DATA_ERROR")) {
            t->m_variableInboundDataError.evaluate(l);
        } else if (comp(variable, "MATCHED_VAR")) {
            t->m_variableMatchedVar.evaluate(l);
        } else if (comp(variable, "MATCHED_VAR_NAME")) {
            t->m_variableMatchedVarName.evaluate(l);
        } else if (comp(variable, "MSC_PCRE_ERROR")) {
            t->m_variableMscPcreError.evaluate(l);
        } else if (comp(variable, "MSC_PCRE_LIMITS_EXCEEDED")) {
            t->m_variableMscPcreLimitsExceeded.evaluate(l);
        } else if (comp(variable, "MULTIPART_CRLF_LF_LINES")) {
            t->m_variableMultipartCrlfLFLines.evaluate(l);
        } else if (comp(variable, "MULTIPART_DATA_AFTER")) {
            t->m_variableMultipartDataAfter.evaluate(l);
        } else if (comp(variable, "MULTIPART_FILE_LIMIT_EXCEEDED")) {
            t->m_variableMultipartFileLimitExceeded.evaluate(l);
        } else if (comp(variable, "MULTIPART_STRICT_ERROR")) {
            t->m_variableMultipartStrictError.evaluate(l);
        } else if (comp(variable, "MULTIPART_HEADER_FOLDING")) {
            t->m_variableMultipartHeaderFolding.evaluate(l);
        } else if (comp(variable, "MULTIPART_INVALID_QUOTING")) {
            t->m_variableMultipartInvalidQuoting.evaluate(l);
        } else if (comp(variable, "MULTIPART_INVALID_HEADER_FOLDING")) {
            t->m_variableMultipartInvalidHeaderFolding.evaluate(l);
        } else if (comp(variable, "MULTIPART_UNMATCHED_BOUNDARY")) {
            t->m_variableMultipartUnmatchedBoundary.evaluate(l);
        } else if (comp(variable, "OUTBOUND_DATA_ERROR")) {
            t->m_variableOutboundDataError.evaluate(l);
        } else if (comp(variable, "PATH_INFO")) {
            t->m_variablePathInfo.evaluate(l);
        } else if (comp(variable, "QUERY_STRING")) {
            t->m_variableQueryString.evaluate(l);
        } else if (comp(variable, "REMOTE_ADDR")) {
            t->m_variableRemoteAddr.evaluate(l);
        } else if (comp(variable, "REMOTE_HOST")) {
            t->m_variableRemoteHost.evaluate(l);
        } else if (comp(variable, "REMOTE_PORT")) {
            t->m_variableRemotePort.evaluate(l);
        } else if (comp(variable, "REQBODY_ERROR")) {
            t->m_variableReqbodyError.evaluate(l);
        } else if (comp(variable, "REQBODY_ERROR_MSG")) {
            t->m_variableReqbodyErrorMsg.evaluate(l);
        } else if (comp(variable, "REQBODY_PROCESSOR_ERROR_MSG")) {
            t->m_variableReqbodyProcessorErrorMsg.evaluate(l);
        } else if (comp(variable, "REQBODY_PROCESSOR_ERROR")) {
            t->m_variableReqbodyProcessorError.evaluate(l);
        } else if (comp(variable, "REQBODY_PROCESSOR")) {
            t->m_variableReqbodyProcessor.evaluate(l);
        } else if (comp(variable, "REQUEST_BASENAME")) {
            t->m_variableRequestBasename.evaluate(l);
        } else if (comp(variable, "REQUEST_BODY")) {
            t->m_variableRequestBody.evaluate(l);
        } else if (comp(variable, "REQUEST_BODY_LENGTH")) {
            t->m_variableRequestBodyLength.evaluate(l);
        } else if (comp(variable, "REQUEST_FILENAME")) {
            t->m_variableRequestFilename.evaluate(l);
        } else if (comp(variable, "REQUEST_LINE")) {
            t->m_variableRequestLine.evaluate(l);
        } else if (comp(variable, "REQUEST_METHOD")) {
            t->m_variableRequestMethod.evaluate(l);
        } else if (comp(variable, "REQUEST_PROTOCOL")) {
            t->m_variableRequestProtocol.evaluate(l);
        } else if (comp(variable, "REQUEST_URI")) {
            t->m_variableRequestURI.evaluate(l);
        } else if (comp(variable, "REQUEST_URI_RAW")) {
            t->m_variableRequestURIRaw.evaluate(l);
        } else if (comp(variable, "RESOURCE")) {
            t->m_variableResource.evaluate(l);
        } else if (comp(variable, "RESPONSE_BODY")) {
            t->m_variableResponseBody.evaluate(l);
        } else if (comp(variable, "RESPONSE_CONTENT_LENGTH")) {
            t->m_variableResponseContentLength.evaluate(l);
        } else if (comp(variable, "RESPONSE_PROTOCOL")) {
            t->m_variableResponseProtocol.evaluate(l);
        } else if (comp(variable, "RESPONSE_STATUS")) {
            t->m_variableResponseStatus.evaluate(l);
        } else if (comp(variable, "SERVER_ADDR")) {
            t->m_variableServerAddr.evaluate(l);
        } else if (comp(variable, "SERVER_NAME")) {
            t->m_variableServerName.evaluate(l);
        } else if (comp(variable, "SERVER_PORT")) {
            t->m_variableServerPort.evaluate(l);
        } else if (comp(variable, "SESSIONID")) {
            t->m_variableSessionID.evaluate(l);
        } else if (comp(variable, "UNIQUE_ID")) {
            t->m_variableUniqueID.evaluate(l);
        } else if (comp(variable, "URLENCODED_ERROR")) {
            t->m_variableUrlEncodedError.evaluate(l);
        } else if (comp(variable, "USERID")) {
            t->m_variableUserID.evaluate(l);
        } else {
            throw std::invalid_argument("Variable not found.");
        }
    }

    static std::string stringMatchResolve(Transaction *t,
        const std::string &variable) {
        std::unique_ptr<std::string> vv = nullptr;
        size_t collection = variable.find(".");
        if (collection == std::string::npos) {
            collection = variable.find(":");
        }
        if (collection == std::string::npos) {
            if (comp(variable, "RESPONSE_CONTENT_TYPE")) {
                vv = t->m_variableResponseContentType.resolveFirst();
            } else if (comp(variable, "ARGS_COMBINED_SIZE")) {
                vv = t->m_variableARGScombinedSize.resolveFirst();
            } else if (comp(variable, "AUTH_TYPE")) {
                vv = t->m_variableAuthType.resolveFirst();
            } else if (comp(variable, "FILES_COMBINED_SIZE")) {
                vv = t->m_variableFilesCombinedSize.resolveFirst();
            } else if (comp(variable, "FULL_REQUEST")) {
                vv = t->m_variableFullRequest.resolveFirst();
            } else if (comp(variable, "FULL_REQUEST_LENGTH")) {
                vv = t->m_variableFullRequestLength.resolveFirst();
            } else if (comp(variable, "INBOUND_DATA_ERROR")) {
                vv = t->m_variableInboundDataError.resolveFirst();
            } else if (comp(variable, "MATCHED_VAR")) {
                vv = t->m_variableMatchedVar.resolveFirst();
            } else if (comp(variable, "MATCHED_VAR_NAME")) {
                vv = t->m_variableMatchedVarName.resolveFirst();
            } else if (comp(variable, "MSC_PCRE_ERROR")) {
                vv = t->m_variableMscPcreError.resolveFirst();
            } else if (comp(variable, "MSC_PCRE_LIMITS_EXCEEDED")) {
                vv = t->m_variableMscPcreLimitsExceeded.resolveFirst();
            } else if (comp(variable, "MULTIPART_CRLF_LF_LINES")) {
                vv = t->m_variableMultipartCrlfLFLines.resolveFirst();
            } else if (comp(variable, "MULTIPART_DATA_AFTER")) {
                vv = t->m_variableMultipartDataAfter.resolveFirst();
            } else if (comp(variable, "MULTIPART_FILE_LIMIT_EXCEEDED")) {
                vv = t->m_variableMultipartFileLimitExceeded.resolveFirst();
            } else if (comp(variable, "MULTIPART_STRICT_ERROR")) {
                vv = t->m_variableMultipartStrictError.resolveFirst();
            } else if (comp(variable, "MULTIPART_HEADER_FOLDING")) {
                vv = t->m_variableMultipartHeaderFolding.resolveFirst();
            } else if (comp(variable, "MULTIPART_INVALID_QUOTING")) {
                vv = t->m_variableMultipartInvalidQuoting.resolveFirst();
            } else if (comp(variable, "MULTIPART_INVALID_HEADER_FOLDING")) {
                vv = t->m_variableMultipartInvalidHeaderFolding.resolveFirst();
            } else if (comp(variable, "MULTIPART_UNMATCHED_BOUNDARY")) {
                vv = t->m_variableMultipartUnmatchedBoundary.resolveFirst();
            } else if (comp(variable, "OUTBOUND_DATA_ERROR")) {
                vv = t->m_variableOutboundDataError.resolveFirst();
            } else if (comp(variable, "PATH_INFO")) {
                vv = t->m_variablePathInfo.resolveFirst();
            } else if (comp(variable, "QUERY_STRING")) {
                vv = t->m_variableQueryString.resolveFirst();
            } else if (comp(variable, "REMOTE_ADDR")) {
                vv = t->m_variableRemoteAddr.resolveFirst();
            } else if (comp(variable, "REMOTE_HOST")) {
                vv = t->m_variableRemoteHost.resolveFirst();
            } else if (comp(variable, "REMOTE_PORT")) {
                vv = t->m_variableRemotePort.resolveFirst();
            } else if (comp(variable, "REQBODY_ERROR")) {
                vv = t->m_variableReqbodyError.resolveFirst();
            } else if (comp(variable, "REQBODY_ERROR_MSG")) {
                vv = t->m_variableReqbodyErrorMsg.resolveFirst();
            } else if (comp(variable, "REQBODY_PROCESSOR_ERROR_MSG")) {
                vv = t->m_variableReqbodyProcessorErrorMsg.resolveFirst();
            } else if (comp(variable, "REQBODY_PROCESSOR_ERROR")) {
                vv = t->m_variableReqbodyProcessorError.resolveFirst();
            } else if (comp(variable, "REQBODY_PROCESSOR")) {
                vv = t->m_variableReqbodyProcessor.resolveFirst();
            } else if (comp(variable, "REQUEST_BASENAME")) {
                vv = t->m_variableRequestBasename.resolveFirst();
            } else if (comp(variable, "REQUEST_BODY")) {
                vv = t->m_variableRequestBody.resolveFirst();
            } else if (comp(variable, "REQUEST_BODY_LENGTH")) {
                vv = t->m_variableRequestBodyLength.resolveFirst();
            } else if (comp(variable, "REQUEST_FILENAME")) {
                vv = t->m_variableRequestFilename.resolveFirst();
            } else if (comp(variable, "REQUEST_LINE")) {
                vv = t->m_variableRequestLine.resolveFirst();
            } else if (comp(variable, "REQUEST_METHOD")) {
                vv = t->m_variableRequestMethod.resolveFirst();
            } else if (comp(variable, "REQUEST_PROTOCOL")) {
                vv = t->m_variableRequestProtocol.resolveFirst();
            } else if (comp(variable, "REQUEST_URI")) {
                vv = t->m_variableRequestURI.resolveFirst();
            } else if (comp(variable, "REQUEST_URI_RAW")) {
                vv = t->m_variableRequestURIRaw.resolveFirst();
            } else if (comp(variable, "RESOURCE")) {
                vv = t->m_variableResource.resolveFirst();
            } else if (comp(variable, "RESPONSE_BODY")) {
                vv = t->m_variableResponseBody.resolveFirst();
            } else if (comp(variable, "RESPONSE_CONTENT_LENGTH")) {
                vv = t->m_variableResponseContentLength.resolveFirst();
            } else if (comp(variable, "RESPONSE_PROTOCOL")) {
                vv = t->m_variableResponseProtocol.resolveFirst();
            } else if (comp(variable, "RESPONSE_STATUS")) {
                vv = t->m_variableResponseStatus.resolveFirst();
            } else if (comp(variable, "SERVER_ADDR")) {
                vv = t->m_variableServerAddr.resolveFirst();
            } else if (comp(variable, "SERVER_NAME")) {
                vv = t->m_variableServerName.resolveFirst();
            } else if (comp(variable, "SERVER_PORT")) {
                vv = t->m_variableServerPort.resolveFirst();
            } else if (comp(variable, "SESSIONID")) {
                vv = t->m_variableSessionID.resolveFirst();
            } else if (comp(variable, "UNIQUE_ID")) {
                vv = t->m_variableUniqueID.resolveFirst();
            } else if (comp(variable, "URLENCODED_ERROR")) {
                vv = t->m_variableUrlEncodedError.resolveFirst();
            } else if (comp(variable, "USERID")) {
                vv = t->m_variableUserID.resolveFirst();
            } else if (comp(variable, "TX")) {
                vv = t->m_collections.m_tx_collection->resolveFirst("");
            } else if (comp(variable, "RESOURCE")) {
                vv = t->m_collections.m_resource_collection->resolveFirst("",
                    t->m_collections.m_resource_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(variable, "USER")) {
                vv = t->m_collections.m_user_collection->resolveFirst("",
                    t->m_collections.m_user_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(variable, "SESSION")) {
                vv = t->m_collections.m_session_collection->resolveFirst("",
                    t->m_collections.m_session_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(variable, "IP")) {
                vv = t->m_collections.m_ip_collection->resolveFirst("",
                    t->m_collections.m_ip_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(variable, "GLOBAL")) {
                vv = t->m_collections.m_global_collection->resolveFirst("",
                    t->m_collections.m_global_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else {
                throw std::invalid_argument("Variable not found.");
            }
        } else {
            std::string col = std::string(variable, 0, collection);
            std::string var = std::string(variable, collection + 1,
                variable.length() - (collection + 1));
            if (comp(col, "ARGS")) {
                vv = t->m_variableArgs.resolveFirst(var);
            } else if (comp(variable, "ARGS_NAMES")) {
                vv = t->m_variableArgsNames.resolveFirst(var);
            } else if (comp(variable, "ARGS_GET_NAMES")) {
                vv = t->m_variableArgsGetNames.resolveFirst(var);
            } else if (comp(variable, "ARGS_POST_NAMES")) {
                vv = t->m_variableArgsPostNames.resolveFirst(var);
            } else if (comp(col, "ARGS_GET")) {
                vv = t->m_variableArgsGet.resolveFirst(var);
            } else if (comp(col, "ARGS_POST")) {
                vv = t->m_variableArgsPost.resolveFirst(var);
            } else if (comp(col, "FILES_SIZES")) {
                vv = t->m_variableFilesSizes.resolveFirst(var);
            } else if (comp(col, "FILES_NAMES")) {
                vv = t->m_variableFilesNames.resolveFirst(var);
            } else if (comp(col, "FILES_TMP_CONTENT")) {
                vv = t->m_variableFilesTmpContent.resolveFirst(var);
            } else if (comp(col, "MULTIPART_FILENAME")) {
                vv = t->m_variableMultipartFileName.resolveFirst(var);
            } else if (comp(col, "MULTIPART_NAME")) {
                vv = t->m_variableMultipartName.resolveFirst(var);
            } else if (comp(col, "MATCHED_VARS_NAMES")) {
                vv = t->m_variableMatchedVarsNames.resolveFirst(var);
            } else if (comp(col, "MATCHED_VARS")) {
                vv = t->m_variableMatchedVars.resolveFirst(var);
            } else if (comp(col, "FILES")) {
                vv = t->m_variableFiles.resolveFirst(var);
            } else if (comp(col, "REQUEST_COOKIES")) {
                vv = t->m_variableRequestCookies.resolveFirst(var);
            } else if (comp(col, "REQUEST_HEADERS")) {
                vv = t->m_variableRequestHeaders.resolveFirst(var);
            } else if (comp(variable, "REQUEST_HEADERS_NAMES")) {
                vv = t->m_variableRequestHeadersNames.resolveFirst(var);
            } else if (comp(col, "RESPONSE_HEADERS")) {
                vv = t->m_variableResponseHeaders.resolveFirst(var);
            } else if (comp(variable, "RESPONSE_HEADERS_NAMES")) {
                vv = t->m_variableResponseHeadersNames.resolveFirst(var);
            } else if (comp(col, "GEO")) {
                vv = t->m_variableGeo.resolveFirst(var);
            } else if (comp(col, "REQUEST_COOKIES_NAMES")) {
                vv = t->m_variableRequestCookiesNames.resolveFirst(var);
            } else if (comp(col, "FILES_TMPNAMES")) {
                vv = t->m_variableFilesTmpNames.resolveFirst(var);
            } else if (comp(col, "MULTIPART_PART_HEADERS")) {
                vv = t->m_variableMultipartPartHeaders.resolveFirst(var);
            } else if (comp(col, "TX")) {
                vv = t->m_collections.m_tx_collection->resolveFirst(var);
            } else if (comp(col, "RESOURCE")) {
                vv = t->m_collections.m_resource_collection->resolveFirst(var,
                    t->m_collections.m_resource_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(col, "USER")) {
                vv = t->m_collections.m_user_collection->resolveFirst(var,
                    t->m_collections.m_user_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(col, "SESSION")) {
                vv = t->m_collections.m_session_collection->resolveFirst(var,
                    t->m_collections.m_session_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(col, "IP")) {
                vv = t->m_collections.m_ip_collection->resolveFirst(var,
                    t->m_collections.m_ip_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else if (comp(col, "GLOBAL")) {
                vv = t->m_collections.m_global_collection->resolveFirst(var,
                    t->m_collections.m_global_collection_key, t->m_rules->m_secWebAppId.m_value);
            } else {
                throw std::invalid_argument("Variable not found.");
            }
        }
        if (vv == nullptr) {
            return std::string("");
        }
        return std::string(*vv.get());
    }
};


class Variable : public VariableMonkeyResolution {
 public:
    explicit Variable(const std::string &name);
    explicit Variable(Variable *_name);
    virtual ~Variable() { }


    virtual void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) = 0;


    bool inline belongsToCollection(Variable *var) {
        return m_collectionName.size() == var->m_collectionName.size()
             && std::equal(m_collectionName.begin(), m_collectionName.end(),
                           var->m_collectionName.begin(),
            [](char aa, char bb) {
            return toupper(aa) == bb;
        });
    }


    void addsKeyExclusion(Variable *v);


    bool operator==(const Variable& b) const {
        return m_collectionName == b.m_collectionName &&
            m_name == b.m_name &&
            *m_fullName == *b.m_fullName;
    }


    std::string& operator+=(const char * p) {  return m_name; }


    std::string m_name;
    std::string m_collectionName;
    std::shared_ptr<std::string> m_fullName;
    KeyExclusions m_keyExclusion;
};

class VariableDictElement : public Variable {
 public:
    VariableDictElement(const std::string &name, const std::string &dict_element)
        :  m_dictElement(dict_element), Variable(name + ":" + dict_element) { }

    std::string m_dictElement;
};


class VariableRegex : public Variable {
 public:
    VariableRegex(const std::string &name, const std::string &regex)
        :  m_r(regex, true),
        m_regex(regex),
        Variable(name + ":" + "regex(" + regex + ")") { }

    Utils::Regex m_r;
    // FIXME: no need for that.
    std::string m_regex;
};

class Variables : public std::vector<Variable *> {
 public:
    bool contains(Variable *v) {
        return std::find_if(begin(), end(),
            [v](const Variable *m) -> bool { return *v == *m; }) != end();
    };
    bool contains(const VariableValue *v) {
        return std::find_if(begin(), end(),
            [v](Variable *m) -> bool {
                VariableRegex *r = dynamic_cast<VariableRegex *>(m);
                if (r) {
                    return r->m_r.searchAll(v->getKey()).size() > 0;
                }
                return v->getKeyWithCollection() == *m->m_fullName.get();
            }) != end();
    };
};


class VariableModificatorExclusion : public Variable {
 public:
    explicit VariableModificatorExclusion(std::unique_ptr<Variable> var)
        : Variable(var.get()),
        m_base(std::move(var)) { }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        m_base->evaluate(t, rule, l);
    }

    std::unique_ptr<Variable> m_base;
};


class VariableModificatorCount : public Variable {
 public:
    explicit VariableModificatorCount(std::unique_ptr<Variable> var)
        : Variable(var.get()),
          m_base(nullptr) {
            m_base.reset(var.release());
        }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        std::vector<const VariableValue *> reslIn;
        VariableValue *val = NULL;
        int count = 0;

        m_base->evaluate(t, rule, &reslIn);

        for (const VariableValue *a : reslIn) {
            count++;
            delete a;
            a = NULL;
        }
        reslIn.clear();

        std::string *res = new std::string(std::to_string(count));
        val = new VariableValue(m_fullName.get(), res);
        delete res;

        l->push_back(val);
        return;
    }

    std::unique_ptr<Variable> m_base;
};


std::string operator+(const std::string &a, modsecurity::variables::Variable *v);
std::string operator+(const std::string &a, modsecurity::variables::Variables *v);


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_VARIABLE_H_
