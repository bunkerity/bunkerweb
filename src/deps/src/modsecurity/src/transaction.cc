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

#include "modsecurity/transaction.h"

#ifdef WITH_YAJL
#include <yajl/yajl_tree.h>
#include <yajl/yajl_gen.h>
#endif

#include <stdio.h>
#include <string.h>

#include <cstdio>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
#include <unordered_map>
#include <vector>

#include "modsecurity/actions/action.h"
#include "src/actions/disruptive/deny.h"
#include "modsecurity/intervention.h"
#include "modsecurity/modsecurity.h"
#include "src/request_body_processor/multipart.h"
#include "src/request_body_processor/xml.h"
#ifdef WITH_YAJL
#include "src/request_body_processor/json.h"
#endif
#include "modsecurity/audit_log.h"
#include "src/unique_id.h"
#include "src/utils/string.h"
#include "src/utils/system.h"
#include "src/utils/decode.h"
#include "src/utils/random.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_message.h"
#include "modsecurity/rules_set_properties.h"
#include "src/actions/disruptive/allow.h"
#include "src/variables/remote_user.h"



using modsecurity::actions::Action;
using modsecurity::RequestBodyProcessor::Multipart;
using modsecurity::RequestBodyProcessor::XML;

namespace modsecurity {

/**
 * @name    Transaction
 * @brief   Represents the inspection on an entire request.
 *
 * An instance of the Transaction class represents an entire request, on its
 * different phases.
 *
 * @param ms ModSecurity core instance.
 * @param rules Rules instance.
 *
 * Example Usage:
 * @code
 *
 * using ModSecurity::ModSecurity;
 * using ModSecurity::Rules;
 * using ModSecurity::Transaction;
 *
 * ModSecurity *modsec;
 * ModSecurity::Rules *rules;
 *
 * modsec = new ModSecurity();
 * rules = new Rules();
 * rules->loadFromUri(rules_file);
 *
 * Transaction *modsecTransaction = new Transaction(modsec, rules);
 * modsecTransaction->processConnection("127.0.0.1", 33333, "127.0.0.1", 8080);
 *
 * if (modsecTransaction->intervention()) {
 *     std::cout << "There is an intervention" << std::endl;
 * }
 *
 * ...
 *
 * delete modsecTransaction;
 *
 * @endcode
 *
 */
Transaction::Transaction(ModSecurity *ms, RulesSet *rules, void *logCbData)
    : m_creationTimeStamp(utils::cpu_seconds()),
     m_clientIpAddress(std::make_shared<std::string>("")),
    m_httpVersion(""),
    m_serverIpAddress(std::make_shared<std::string>("")),
    m_uri(""),
    m_uri_no_query_string_decoded(std::make_shared<std::string>("")),
    m_ARGScombinedSizeDouble(0),
    m_clientPort(0),
    m_highestSeverityAction(255),
    m_httpCodeReturned(200),
    m_serverPort(0),
    m_ms(ms),
    m_requestBodyType(UnknownFormat),
    m_requestBodyProcessor(UnknownFormat),
    m_rules(rules),
    m_ruleRemoveById(),
    m_ruleRemoveByIdRange(),
    m_ruleRemoveByTag(),
    m_ruleRemoveTargetByTag(),
    m_ruleRemoveTargetById(),
    m_requestBodyAccess(RulesSet::PropertyNotSetConfigBoolean),
    m_auditLogModifier(),
    m_ctlAuditEngine(AuditLog::AuditLogStatus::NotSetLogStatus),
    m_rulesMessages(),
    m_requestBody(),
    m_responseBody(),
    /* m_id(), */
    m_skip_next(0),
    m_allowType(modsecurity::actions::disruptive::NoneAllowType),
    m_uri_decoded(""),
    m_actions(),
    m_it(),
    m_timeStamp(std::time(NULL)),
    m_collections(ms->m_global_collection, ms->m_ip_collection,
        ms->m_session_collection, ms->m_user_collection,
        ms->m_resource_collection),
    m_matched(),
#ifdef WITH_LIBXML2
    m_xml(new RequestBodyProcessor::XML(this)),
#else
    m_xml(NULL),
#endif
#ifdef WITH_YAJL
    m_json(new RequestBodyProcessor::JSON(this)),
#else
    m_json(NULL),
#endif
    m_secRuleEngine(RulesSetProperties::PropertyNotSetRuleEngine),
    m_variableDuration(""),
    m_variableEnvs(),
    m_variableHighestSeverityAction(""),
    m_variableRemoteUser(""),
    m_variableTime(""),
    m_variableTimeDay(""),
    m_variableTimeEpoch(""),
    m_variableTimeHour(""),
    m_variableTimeMin(""),
    m_variableTimeSec(""),
    m_variableTimeWDay(""),
    m_variableTimeYear(""),
    m_logCbData(logCbData),
    TransactionAnchoredVariables(this) {
    m_id = std::unique_ptr<std::string>( new std::string(
        std::to_string(m_timeStamp)
        + std::to_string(modsecurity::utils::generate_transaction_unique_id())));

    m_variableUrlEncodedError.set("0", 0);

    ms_dbg(4, "Initializing transaction");

    intervention::clean(&m_it);
}

Transaction::Transaction(ModSecurity *ms, RulesSet *rules, char *id, void *logCbData)
    : m_creationTimeStamp(utils::cpu_seconds()),
    m_clientIpAddress(std::make_shared<std::string>("")),
    m_httpVersion(""),
    m_serverIpAddress(std::make_shared<std::string>("")),
    m_uri(""),
    m_uri_no_query_string_decoded(std::make_shared<std::string>("")),
    m_ARGScombinedSizeDouble(0),
    m_clientPort(0),
    m_highestSeverityAction(255),
    m_httpCodeReturned(200),
    m_serverPort(0),
    m_ms(ms),
    m_requestBodyType(UnknownFormat),
    m_requestBodyProcessor(UnknownFormat),
    m_rules(rules),
    m_ruleRemoveById(),
    m_ruleRemoveByIdRange(),
    m_ruleRemoveByTag(),
    m_ruleRemoveTargetByTag(),
    m_ruleRemoveTargetById(),
    m_requestBodyAccess(RulesSet::PropertyNotSetConfigBoolean),
    m_auditLogModifier(),
    m_ctlAuditEngine(AuditLog::AuditLogStatus::NotSetLogStatus),
    m_rulesMessages(),
    m_requestBody(),
    m_responseBody(),
    m_id(std::unique_ptr<std::string>(new std::string(id))),
    m_skip_next(0),
    m_allowType(modsecurity::actions::disruptive::NoneAllowType),
    m_uri_decoded(""),
    m_actions(),
    m_it(),
    m_timeStamp(std::time(NULL)),
    m_collections(ms->m_global_collection, ms->m_ip_collection,
        ms->m_session_collection, ms->m_user_collection,
        ms->m_resource_collection),
    m_matched(),
#ifdef WITH_LIBXML2
    m_xml(new RequestBodyProcessor::XML(this)),
#else
    m_xml(NULL),
#endif
#ifdef WITH_YAJL
    m_json(new RequestBodyProcessor::JSON(this)),
#else
    m_json(NULL),
#endif
    m_secRuleEngine(RulesSetProperties::PropertyNotSetRuleEngine),
    m_variableDuration(""),
    m_variableEnvs(),
    m_variableHighestSeverityAction(""),
    m_variableRemoteUser(""),
    m_variableTime(""),
    m_variableTimeDay(""),
    m_variableTimeEpoch(""),
    m_variableTimeHour(""),
    m_variableTimeMin(""),
    m_variableTimeSec(""),
    m_variableTimeWDay(""),
    m_variableTimeYear(""),
    m_logCbData(logCbData),
    TransactionAnchoredVariables(this) {

    m_variableUrlEncodedError.set("0", 0);

    ms_dbg(4, "Initializing transaction");

    intervention::clean(&m_it);
}


Transaction::~Transaction() {
    m_responseBody.str(std::string());
    m_responseBody.clear();

    m_requestBody.str(std::string());
    m_requestBody.clear();

    m_rulesMessages.clear();

    intervention::free(&m_it);
    intervention::clean(&m_it);

#ifdef WITH_YAJL
    delete m_json;
#endif
#ifdef WITH_LIBXML2
    delete m_xml;
#endif
}


/**
 * @name    debug
 * @brief   Prints a message on the debug logs.
 *
 * Debug logs are important during the rules creation phase, this method can be
 * used to print message on this debug log.
 * 
 * @param level Debug level, current supported from 0 to 9.
 * @param message Message to be logged.
 *
 */
#ifndef NO_LOGS
void Transaction::debug(int level, const std::string& message) const {
    if (m_rules == NULL) {
        return;
    }

    m_rules->debug(level, *m_id.get(), m_uri, message);
}
#endif

/**
 * @name    processConnection
 * @brief   Perform the analysis on the connection.
 *
 * This method should be called at very beginning of a request process, it is
 * expected to be executed prior to the virtual host resolution, when the
 * connection arrives on the server.
 *
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity Transaction.
 * @param client Client's IP address in text format.
 * @param cPort Client's port
 * @param server Server's IP address in text format.
 * @param sPort Server's port
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processConnection(const char *client, int cPort,
    const char *server, int sPort) {
    m_clientIpAddress = std::unique_ptr<std::string>(new std::string(client));
    m_serverIpAddress = std::unique_ptr<std::string>(new std::string(server));
    this->m_clientPort = cPort;
    this->m_serverPort = sPort;
    ms_dbg(4, "Transaction context created.");
    ms_dbg(4, "Starting phase CONNECTION. (SecRules 0)");


    m_variableRemoteHost.set(*m_clientIpAddress.get(), m_variableOffset);
    m_variableUniqueID.set(*m_id.get(), m_variableOffset);
    m_variableRemoteAddr.set(*m_clientIpAddress.get(), m_variableOffset);
    m_variableServerAddr.set(*m_serverIpAddress.get(), m_variableOffset);
    m_variableServerPort.set(std::to_string(this->m_serverPort),
        m_variableOffset);
    m_variableRemotePort.set(std::to_string(this->m_clientPort),
        m_variableOffset);

    this->m_rules->evaluate(modsecurity::ConnectionPhase, this);
    return true;
}


bool Transaction::extractArguments(const std::string &orig,
    const std::string& buf, size_t offset) {
    char sep1 = '&';
    if (m_rules->m_secArgumentSeparator.m_set) {
        sep1 = m_rules->m_secArgumentSeparator.m_value.at(0);
    }
    std::vector<std::string> key_value_sets = utils::string::ssplit(buf, sep1);

    for (std::string t : key_value_sets) {
        char sep2 = '=';
        size_t key_s = 0;
        size_t value_s = 0;
        int invalid = 0;
        int changed = 0;

        std::string key;
        std::string value;
        std::pair<std::string, std::string> key_value_pair = utils::string::ssplit_pair(t, sep2);
        key = key_value_pair.first;
        value = key_value_pair.second;

        key_s = (key.length() + 1);
        value_s = (value.length() + 1);
        unsigned char *key_c = reinterpret_cast<unsigned char *>(
            calloc(sizeof(char), key_s));
        unsigned char *value_c = reinterpret_cast<unsigned char *>(
            calloc(sizeof(char), value_s));

        memcpy(key_c, key.c_str(), key_s);
        memcpy(value_c, value.c_str(), value_s);

        key_s = utils::urldecode_nonstrict_inplace(key_c, key_s,
            &invalid, &changed);
        value_s = utils::urldecode_nonstrict_inplace(value_c, value_s,
            &invalid, &changed);

        if (invalid) {
            m_variableUrlEncodedError.set("1", m_variableOffset);
        }

        addArgument(orig, std::string(reinterpret_cast<char *>(key_c), key_s-1),
            std::string(reinterpret_cast<char *>(value_c), value_s-1), offset);
        offset = offset + t.size() + 1;

        free(key_c);
        free(value_c);
    }

    return true;
}


bool Transaction::addArgument(const std::string& orig, const std::string& key,
    const std::string& value, size_t offset) {
    ms_dbg(4, "Adding request argument (" + orig + "): name \"" + \
                key + "\", value \"" + value + "\"");

    if (m_rules->m_argumentsLimit.m_set
            && m_variableArgs.size() >= m_rules->m_argumentsLimit.m_value) {
        ms_dbg(4, "Skipping request argument, over limit (" + std::to_string(m_rules->m_argumentsLimit.m_value) + ")")
        return false;
    }

    offset = offset + key.size() + 1;
    m_variableArgs.set(key, value, offset);

    if (orig == "GET") {
        m_variableArgsGet.set(key, value, offset);
    } else if (orig == "POST") {
        m_variableArgsPost.set(key, value, offset);
    }

    m_ARGScombinedSizeDouble = m_ARGScombinedSizeDouble + \
        key.length() + value.length();

    m_variableARGScombinedSize.set(std::to_string(m_ARGScombinedSizeDouble),
        offset - key.size() - 1, key.size());
    m_variableARGScombinedSize.set(std::to_string(m_ARGScombinedSizeDouble),
        offset, value.length());

    return true;
}


/**
 * @name    processURI
 * @brief   Perform the analysis on the URI and all the query string variables.
 *
 * This method should be called at very beginning of a request process, it is
 * expected to be executed prior to the virtual host resolution, when the
 * connection arrives on the server.
 *
 * @note There is no direct connection between this function and any phase of
 *       the SecLanguage's phases. It is something that may occur between the
 *       SecLanguage phase 1 and 2.
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 * @param uri   Uri.
 * @param method   Method (GET, POST, PUT).
 * @param http_version   Http version (1.0, 1.1, 2.0).
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processURI(const char *uri, const char *method,
    const char *http_version) {

    ms_dbg(4, "Starting phase URI. (SecRules 0 + 1/2)");

    m_httpVersion = http_version;
    m_uri = uri;
    std::string uri_s(uri);

    // any uri-fragment that was received should only be retained in
    // - m_uri
    // - m_variableRequestURIRaw
    // - m_variableRequestLine
    size_t pos_raw_fragment = uri_s.find("#");
    if (pos_raw_fragment != std::string::npos) {
        uri_s = uri_s.substr(0, pos_raw_fragment);
    }

    size_t pos_raw_query = uri_s.find("?");

    m_uri_decoded = utils::uri_decode(uri_s);

    size_t var_size = pos_raw_query;

    m_variableRequestMethod.set(method, 0);


    std::string requestLine(std::string(method) + " " + std::string(uri));
    m_variableRequestLine.set(requestLine \
        + " HTTP/" + std::string(http_version), m_variableOffset);

    m_variableRequestProtocol.set("HTTP/" + std::string(http_version),
        m_variableOffset + requestLine.size() + 1);


    size_t pos_query = m_uri_decoded.find("?");
    if (pos_query != std::string::npos) {
        m_uri_no_query_string_decoded = std::unique_ptr<std::string>(
            new std::string(m_uri_decoded, 0, pos_query));
    } else {
        m_uri_no_query_string_decoded = std::unique_ptr<std::string>(
            new std::string(m_uri_decoded));
    }


    if (pos_raw_query != std::string::npos) {
        std::string qry = std::string(uri_s, pos_raw_query + 1,
            uri_s.length() - (pos_raw_query + 1));
        m_variableQueryString.set(qry, pos_raw_query + 1
            + std::string(method).size() + 1);
    }

    std::string path_info;
    if (pos_query == std::string::npos) {
        path_info = std::string(m_uri_decoded, 0);
    } else {
        path_info = std::string(m_uri_decoded, 0, pos_query);
    }
    if (var_size == std::string::npos) {
        var_size = uri_s.size();
    }

    m_variablePathInfo.set(path_info, m_variableOffset + strlen(method) +
        1, var_size);
    m_variableRequestFilename.set(path_info,  m_variableOffset +
        strlen(method) + 1, var_size);


    size_t offset = path_info.find_last_of("/\\");
    if (offset != std::string::npos && path_info.length() > offset + 1) {
        std::string basename = std::string(path_info, offset + 1,
            path_info.length() - (offset + 1));
        m_variableRequestBasename.set(basename, m_variableOffset +
            strlen(method) + 1 + offset + 1);
    }

    m_variableOffset = m_variableRequestLine.m_value.size();

    std::string parsedURI = m_uri_decoded;
    // The more popular case is without domain
    if (!m_uri_decoded.empty() && m_uri_decoded.at(0) != '/') {
        bool fullDomain = true;
        size_t scheme = m_uri_decoded.find(":")+1;
        if (scheme == std::string::npos) {
            fullDomain = false;
        }
        // Searching with a pos of -1 is undefined we also shortcut
        if (scheme != std::string::npos && fullDomain == true) {
            // Assuming we found a colon make sure its followed
            size_t netloc = m_uri_decoded.find("//", scheme) + 2;
            if (netloc == std::string::npos || (netloc != scheme + 2)) {
                fullDomain = false;
            }
            if (netloc != std::string::npos && fullDomain == true) {
                size_t path = m_uri_decoded.find("/", netloc);
                if (path != std::string::npos) {
                    parsedURI = m_uri_decoded.substr(path);
                }
            }
        }
    }

    m_variableRequestURI.set(parsedURI, std::string(method).size() + 1,
        uri_s.size());
    m_variableRequestURIRaw.set(uri, std::string(method).size() + 1);

    if (m_variableQueryString.m_value.empty() == false) {
        extractArguments("GET", m_variableQueryString.m_value,
            m_variableQueryString.m_offset);
    }

    m_variableOffset = m_variableOffset + 1;
    return true;
}


/**
 * @name    processRequestHeaders
 * @brief   Perform the analysis on the request readers.
 *
 * This method perform the analysis on the request headers, notice however
 * that the headers should be added prior to the execution of this function.
 *
 * @note Remember to check for a possible intervention.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processRequestHeaders() {
    ms_dbg(4, "Starting phase REQUEST_HEADERS.  (SecRules 1)");

    if (getRuleEngineState() == RulesSet::DisabledRuleEngine) {
        ms_dbg(4, "Rule engine disabled, returning...");
        return true;
    }

    this->m_rules->evaluate(modsecurity::RequestHeadersPhase, this);

    return true;
}


/**
 * @name    addRequestHeader
 * @brief   Adds a request header
 *
 * With this method it is possible to feed ModSecurity with a request header.
 *
 * @note This function expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param key   header name.
 * @param value header value.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::addRequestHeader(const std::string& key,
    const std::string& value) {
    m_variableRequestHeadersNames.set(key, key, m_variableOffset);

    m_variableOffset = m_variableOffset + key.size() + 2;
    m_variableRequestHeaders.set(key, value, m_variableOffset);


    std::string keyl = utils::string::tolower(key);
    if (keyl == "authorization") {
        std::vector<std::string> type = utils::string::split(value, ' ');
        m_variableAuthType.set(type[0], m_variableOffset);
    }

    if (keyl == "cookie") {
        size_t localOffset = m_variableOffset;
        size_t pos;

        std::vector<std::string> cookies = utils::string::ssplit(value, ';');

        if (!cookies.empty()) {
            // Get rid of any optional whitespace after the cookie-string
            // (i.e. after the end of the final cookie-pair)
            std::string& final_cookie_pair = cookies.back();
            while (!final_cookie_pair.empty() && isspace(final_cookie_pair.back())) {
                final_cookie_pair.pop_back();
            }
        }

        for (const std::string &c : cookies) {
            // skip empty substring, eg "Cookie: ;;foo=bar"
            if (c.empty() == true) {
                localOffset++; // add length of ';'
                continue;
            }

            // find the first '='
            pos = c.find_first_of("=", 0);
            std::string ckey = "";
            std::string cval = "";

            // if the cookie doesn't contains '=', its just a key
            if (pos == std::string::npos) {
                ckey = c;
            }
            // else split to two substrings by first =
            else {
                ckey = c.substr(0, pos);
                // value will contains the next '=' chars if exists
                // eg. foo=bar=baz -> key: foo, value: bar=baz
                cval = c.substr(pos+1);
            }

            // ltrim the key - following the modsec v2 way
            while (ckey.empty() == false && isspace(ckey.at(0))) {
                ckey.erase(0, 1);
                localOffset++;
            }

            // if the key is empty (eg: "Cookie:   =bar;") skip it
            if (ckey.empty() == true) {
                localOffset = localOffset + c.length() + 1;
                continue;
            }
            else {
                // handle cookie only if the key is not empty
                // set cookie name
                m_variableRequestCookiesNames.set(ckey,
                        ckey, localOffset);
                localOffset = localOffset + ckey.size() + 1;
                // set cookie value
                m_variableRequestCookies.set(ckey, cval,
                        localOffset);
                localOffset = localOffset + cval.size() + 1;
            }
        }
    }
    /**
     * Simple check to decide the request body content. This is not the right
     * place, the "body processor" should be able to tell what he is capable
     * to deal with.
     *
     */

    if (keyl == "content-type") {
        std::string multipart("multipart/form-data");
        std::string urlencoded("application/x-www-form-urlencoded");
        std::string l = utils::string::tolower(value);
        if (l.compare(0, multipart.length(), multipart) == 0) {
            this->m_requestBodyType = MultiPartRequestBody;
            m_variableReqbodyProcessor.set("MULTIPART", m_variableOffset);
        }

        if (l.compare(0, urlencoded.length(), urlencoded) == 0) {
            this->m_requestBodyType = WWWFormUrlEncoded;
            m_variableReqbodyProcessor.set("URLENCODED", m_variableOffset);
        }
    }

    if (keyl == "host") {
        std::vector<std::string> host = utils::string::split(value, ':');
        m_variableServerName.set(host[0], m_variableOffset);
    }
    m_variableOffset = m_variableOffset + value.size() + 1;

    return 1;
}


/**
 * @name    addRequestHeader
 * @brief   Adds a request header
 *
 * With this method it is possible to feed ModSecurity with a request header.
 *
 * @note This function expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param key   header name.
 * @param value header value.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::addRequestHeader(const unsigned char *key,
    const unsigned char *value) {
    return this->addRequestHeader(key,
        strlen(reinterpret_cast<const char *>(key)),
        value,
        strlen(reinterpret_cast<const char *>(value)));
}


/**
 * @name    addRequestHeader
 * @brief   Adds a request header
 *
 * Do not expect a NULL terminated string, instead it expect the string and the
 * string size, for the value and key.
 *
 * @param transaction   ModSecurity transaction.
 * @param key     header name.
 * @param key_n   header name size.
 * @param value   header value.
 * @param value_n header value size.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
int Transaction::addRequestHeader(const unsigned char *key, size_t key_n,
    const unsigned char *value, size_t value_n) {
    std::string keys;
    std::string values;

    keys.assign(reinterpret_cast<const char *>(key), key_n);
    values.assign(reinterpret_cast<const char *>(value), value_n);

    return this->addRequestHeader(keys, values);
}


/**
 * @name    processRequestBody
 * @brief   Perform the request body (if any)
 *
 * This method perform the analysis on the request body. It is optional to
 * call that function. If this API consumer already know that there isn't a
 * body for inspect it is recommended to skip this step.
 *
 * @note It is necessary to "append" the request body prior to the execution
 *       of this function.
 * @note Remember to check for a possible intervention.
 * 
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processRequestBody() {
    ms_dbg(4, "Starting phase REQUEST_BODY. (SecRules 2)");

    if (getRuleEngineState() == RulesSetProperties::DisabledRuleEngine) {
        ms_dbg(4, "Rule engine disabled, returning...");
        return true;
    }

    if (m_variableInboundDataError.m_value.empty() == true) {
        m_variableInboundDataError.set("0", 0);
    }

    /*
     * Process the request body even if there is nothing to be done.
     * 
     * if (m_requestBody.tellp() <= 0) {
     *     return true;
     * }
     * 
     */
    std::unique_ptr<std::string> a = m_variableRequestHeaders.resolveFirst(
        "Content-Type");

    bool requestBodyNoFilesLimitExceeded = false;
    if ((m_requestBodyType == WWWFormUrlEncoded) ||
        (m_requestBodyProcessor == JSONRequestBody) ||
        (m_requestBodyProcessor == XMLRequestBody)) {
        if ((m_rules->m_requestBodyNoFilesLimit.m_set)
            && (m_requestBody.str().size() > m_rules->m_requestBodyNoFilesLimit.m_value)) {
            m_variableReqbodyError.set("1", 0);
            m_variableReqbodyErrorMsg.set("Request body excluding files is bigger than the maximum expected.", 0);
            m_variableInboundDataError.set("1", m_variableOffset);
            ms_dbg(5, "Request body excluding files is bigger than the maximum expected. Limit: " \
                + std::to_string(m_rules->m_requestBodyNoFilesLimit.m_value));
            requestBodyNoFilesLimitExceeded = true;
	}
    }

#ifdef WITH_LIBXML2
    if (m_requestBodyProcessor == XMLRequestBody) {
        // large size might cause issues in the parsing itself; omit if exceeded
        if (!requestBodyNoFilesLimitExceeded) {
            std::string error;
            if (m_xml->init() == true) {
                m_xml->processChunk(m_requestBody.str().c_str(),
                    m_requestBody.str().size(),
                    &error);
                m_xml->complete(&error);
            }
            if (error.empty() == false) {
                m_variableReqbodyError.set("1", m_variableOffset);
                m_variableReqbodyErrorMsg.set("XML parsing error: " + error,
                    m_variableOffset);
                m_variableReqbodyProcessorErrorMsg.set("XML parsing error: " \
                    + error, m_variableOffset);
                m_variableReqbodyProcessorError.set("1", m_variableOffset);
            } else {
                m_variableReqbodyError.set("0", m_variableOffset);
                m_variableReqbodyProcessorError.set("0", m_variableOffset);
            }
        }
#endif
#if WITH_YAJL
#ifdef WITH_LIBXML2
    } else if (m_requestBodyProcessor == JSONRequestBody) {
#else
    if (m_requestBodyProcessor == JSONRequestBody) {
#endif
        // large size might cause issues in the parsing itself; omit if exceeded
        if (!requestBodyNoFilesLimitExceeded) {
            std::string error;
            if (m_rules->m_requestBodyJsonDepthLimit.m_set) {
                m_json->setMaxDepth(m_rules->m_requestBodyJsonDepthLimit.m_value);
            }
            if (m_json->init() == true) {
                m_json->processChunk(m_requestBody.str().c_str(),
                    m_requestBody.str().size(),
                    &error);
                m_json->complete(&error);
            }
            if (error.empty() == false && m_requestBody.str().size() > 0) {
                m_variableReqbodyError.set("1", m_variableOffset);
                m_variableReqbodyProcessorError.set("1", m_variableOffset);
                m_variableReqbodyErrorMsg.set("JSON parsing error: " + error,
                    m_variableOffset);
                m_variableReqbodyProcessorErrorMsg.set("JSON parsing error: " \
                    + error, m_variableOffset);
            } else {
                m_variableReqbodyError.set("0", m_variableOffset);
                m_variableReqbodyProcessorError.set("0", m_variableOffset);
            }
        }
#endif
#if defined(WITH_LIBXML2) or defined(WITH_YAJL)
    } else if (m_requestBodyType == MultiPartRequestBody) {
#else
    if (m_requestBodyType == MultiPartRequestBody) {
#endif
        std::string error;
        int reqbodyNoFilesLength = 0;
        if (a != NULL) {
            Multipart m(*a, this);
            if (m.init(&error) == true) {
                m.process(m_requestBody.str(), &error, m_variableOffset);
            }
            reqbodyNoFilesLength = m.m_reqbody_no_files_length;
            m.multipart_complete(&error);
        }
        if (error.empty() == false) {
            m_variableReqbodyError.set("1", m_variableOffset);
            m_variableReqbodyProcessorError.set("1", m_variableOffset);
            m_variableReqbodyErrorMsg.set("Multipart parsing error: " + error,
                m_variableOffset);
            m_variableReqbodyProcessorErrorMsg.set("Multipart parsing " \
                "error: " + error, m_variableOffset);
        } else if (((m_rules->m_requestBodyNoFilesLimit.m_set)
                   && (reqbodyNoFilesLength > m_rules->m_requestBodyNoFilesLimit.m_value))) {
            m_variableReqbodyError.set("1", 0);
            m_variableReqbodyErrorMsg.set("Request body excluding files is bigger than the maximum expected.", 0);
            m_variableInboundDataError.set("1", m_variableOffset);
            ms_dbg(5, "Request body excluding files is bigger than the maximum expected. Limit: " \
                + std::to_string(m_rules->m_requestBodyNoFilesLimit.m_value));
        } else {
            m_variableReqbodyError.set("0", m_variableOffset);
            m_variableReqbodyProcessorError.set("0", m_variableOffset);
        }
    } else if (m_requestBodyType == WWWFormUrlEncoded) {
        m_variableOffset++;
        // large size might cause issues in the parsing itself; omit if exceeded
        if (!requestBodyNoFilesLimitExceeded) {
            extractArguments("POST", m_requestBody.str(), m_variableOffset);
	}
    } else if (m_requestBodyType != UnknownFormat) {
        /**
         * FIXME: double check to see if that is a valid scenario...
         *
         */
        std::string error;
        if (a != NULL && a->empty() == false) {
            error.assign(*a);
        }

        m_variableReqbodyError.set("1", m_variableOffset);
        m_variableReqbodyProcessorError.set("1", m_variableOffset);
        m_variableReqbodyErrorMsg.set("Unknown request body processor: " \
            + error, m_variableOffset);
        m_variableReqbodyProcessorErrorMsg.set("Unknown request body " \
            "processor: " + error, m_variableOffset);
    } else {
        m_variableReqbodyError.set("0", m_variableOffset);
        m_variableReqbodyProcessorError.set("0", m_variableOffset);
    }

    if (m_rules->m_secRequestBodyAccess == RulesSetProperties::FalseConfigBoolean) {
        if (m_requestBodyAccess != RulesSetProperties::TrueConfigBoolean) {
            ms_dbg(4, "Request body processing is disabled");
            return true;
        } else {
            ms_dbg(4, "Request body processing is disabled, but " \
                "enabled to this transaction due to ctl:requestBodyAccess " \
                "action");
        }
    } else {
        if (m_requestBodyAccess == RulesSetProperties::FalseConfigBoolean) {
            ms_dbg(4, "Request body processing is enabled, but " \
                "disabled to this transaction due to ctl:requestBodyAccess " \
                "action");
            return true;
        }
    }

    /**
     * FIXME: This variable should be calculated on demand, it is
     * computationally intensive.
     */
    std::string fullRequest;
    std::vector<const VariableValue *> l;
    m_variableRequestHeaders.resolve(&l);
    for (auto &h : l) {
        fullRequest = fullRequest + h->getKey() + ": " + h->getValue() + "\n";
        delete h;
    }

    fullRequest = fullRequest + "\n\n";
    fullRequest = fullRequest + m_requestBody.str();
    m_variableFullRequest.set(fullRequest, m_variableOffset);
    m_variableFullRequestLength.set(std::to_string(fullRequest.size()),
        m_variableOffset);

    if (m_requestBody.tellp() > 0) {
        m_variableRequestBody.set(m_requestBody.str(), m_variableOffset);
        m_variableRequestBodyLength.set(std::to_string(
            m_requestBody.str().size()),
            m_variableOffset, m_requestBody.str().size());
    }

    this->m_rules->evaluate(modsecurity::RequestBodyPhase, this);
    return true;
}


/**
 * @name    appendRequestBody
 * @brief   Adds request body to be inspected.
 *
 * With this method it is possible to feed ModSecurity with data for
 * inspection regarding the request body. There are two possibilities here:
 * 
 * 1 - Adds the buffer in a row;
 * 2 - Adds it in chunks;
 *
 * A third option should be developed which is share your application buffer.
 * In any case, remember that the utilization of this function may reduce your
 * server throughput, as this buffer creations is computationally expensive.
 *
 * @note While feeding ModSecurity remember to keep checking if there is an
 *       intervention, Sec Language has the capability to set the maximum
 *       inspection size which may be reached, and the decision on what to do
 *       in this case is upon the rules.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::requestBodyFromFile(const char *path) {
    std::ifstream request_body(path);
    std::string str;

    if (request_body.is_open() == false) {
        ms_dbg(3, "Failed to open request body at: " + std::string(path));
        return false;
    }

    request_body.seekg(0, std::ios::end);
    try {
        str.reserve(request_body.tellg());
    } catch (...) {
        ms_dbg(3, "Failed to allocate memory to load request body.");
        return false;
    }
    request_body.seekg(0, std::ios::beg);
    str.assign((std::istreambuf_iterator<char>(request_body)),
            std::istreambuf_iterator<char>());

    const char *buf = str.c_str();
    int len = request_body.tellg();

    ms_dbg(9, "Adding request body: " + std::to_string(len) + " bytes. " \
        "Limit set to: "
        + std::to_string(this->m_rules->m_requestBodyLimit.m_value));

    return appendRequestBody(reinterpret_cast<const unsigned char*>(buf), len);
}

int Transaction::appendRequestBody(const unsigned char *buf, size_t len) {
    int current_size = this->m_requestBody.tellp();

    ms_dbg(9, "Appending request body: " + std::to_string(len) + " bytes. " \
        "Limit set to: "
        + std::to_string(this->m_rules->m_requestBodyLimit.m_value));

    if (this->m_rules->m_requestBodyLimit.m_value > 0
        && this->m_rules->m_requestBodyLimit.m_value < len + current_size) {
        m_variableInboundDataError.set("1", m_variableOffset);
        ms_dbg(5, "Request body is bigger than the maximum expected.");

        if (this->m_rules->m_requestBodyLimitAction ==
            RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction) {
            size_t spaceLeft = this->m_rules->m_requestBodyLimit.m_value
                - current_size;
            this->m_requestBody.write(reinterpret_cast<const char*>(buf),
                spaceLeft);
            ms_dbg(5, "Request body limit is marked to process partial");
            return false;
        } else {
            if (this->m_rules->m_requestBodyLimitAction ==
                RulesSet::BodyLimitAction::RejectBodyLimitAction) {
                ms_dbg(5, "Request body limit is marked to reject the " \
                    "request");
                if (getRuleEngineState() == RulesSet::EnabledRuleEngine) {
                    intervention::free(&m_it);
                    m_it.log = strdup("Request body limit is marked to " \
                            "reject the request");
                    m_it.status = 403;
                    m_it.disruptive = true;
                } else {
                    ms_dbg(5, "Not rejecting the request as the engine is " \
                        "not Enabled");
                }
            }
            return true;
        }
    }

    this->m_requestBody.write(reinterpret_cast<const char*>(buf), len);

    return true;
}


/**
 * @name    processResponseHeaders
 * @brief   Perform the analysis on the response readers.
 *
 * This method perform the analysis on the response headers, notice however
 * that the headers should be added prior to the execution of this function.
 *
 * @note Remember to check for a possible intervention.
 *
 * @param code The returned http code.
 * @param proto Protocol used on the response.
 * 
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processResponseHeaders(int code, const std::string& proto) {
    ms_dbg(4, "Starting phase RESPONSE_HEADERS. (SecRules 3)");

    this->m_httpCodeReturned = code;
    m_variableResponseStatus.set(std::to_string(code), m_variableOffset);
    m_variableResponseProtocol.set(proto, m_variableOffset);

    if (getRuleEngineState() == RulesSet::DisabledRuleEngine) {
        ms_dbg(4, "Rule engine disabled, returning...");
        return true;
    }

    this->m_rules->evaluate(modsecurity::ResponseHeadersPhase, this);
    return true;
}


/**
 * @name    addResponseHeader
 * @brief   Adds a response header
 *
 * With this method it is possible to feed ModSecurity with a response
 * header.
 *
 * @note This method expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param key     header name.
 * @param value   header value.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::addResponseHeader(const std::string& key,
    const std::string& value) {
    m_variableResponseHeadersNames.set(key, key, m_variableOffset);
    m_variableResponseHeaders.set(key, value, m_variableOffset);

    if (utils::string::tolower(key) == "content-type") {
        // Removes the charset=...
        // Content-Type: text/html; charset=UTF-8
        std::vector<std::string> val = utils::string::split(value, ';');
        if (val.size() > 0) {
            m_variableResponseContentType.set(val[0], 0);
        }
    }
    return 1;
}


/**
 * @name    addResponseHeader
 * @brief   Adds a response header
 *
 * With this method it is possible to feed ModSecurity with a response
 * header.
 *
 * @note This method expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param key     header name.
 * @param value   header value.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::addResponseHeader(const unsigned char *key,
    const unsigned char *value) {
    return this->addResponseHeader(key,
        strlen(reinterpret_cast<const char *>(key)),
        value,
        strlen(reinterpret_cast<const char *>(value)));
}


/**
 * @name    msc_add_n_response_header
 * @brief   Adds a response header
 *
 * Do not expect a NULL terminated string, instead it expect the string and the
 * string size, for the value and key.
 *
 * @param key     header name.
 * @param key_n   header name size.
 * @param value   header value.
 * @param value_n header value size.
 * 
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::addResponseHeader(const unsigned char *key, size_t key_n,
    const unsigned char *value, size_t value_n) {
    std::string keys;
    std::string values;

    keys.assign(reinterpret_cast<const char *>(key), key_n);
    values.assign(reinterpret_cast<const char *>(value), value_n);

    return this->addResponseHeader(keys, values);
}


/**
 * @name    processResponseBody
 * @brief   Perform the request body (if any)
 *
 * This method perform the analysis on the request body. It is optional to
 * call that method. If this API consumer already know that there isn't a
 * body for inspect it is recommended to skip this step.
 *
 * @note It is necessary to "append" the request body prior to the execution
 *       of this method.
 * @note Remember to check for a possible intervention.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processResponseBody() {
    ms_dbg(4, "Starting phase RESPONSE_BODY. (SecRules 4)");

    if (getRuleEngineState() == RulesSet::DisabledRuleEngine) {
        ms_dbg(4, "Rule engine disabled, returning...");
        return true;
    }

    if (m_rules->m_secResponseBodyAccess != RulesSetProperties::TrueConfigBoolean) {
        ms_dbg(4, "Response body is disabled, returning... " + std::to_string(m_rules->m_secResponseBodyAccess));
        return true;
    }

    std::set<std::string> &bi = \
        m_rules->m_responseBodyTypeToBeInspected.m_value;
    auto t = bi.find(m_variableResponseContentType.m_value);
    if (t == bi.end()
        && m_rules->m_responseBodyTypeToBeInspected.m_set == true) {
        ms_dbg(5, "Response Content-Type is " \
            + m_variableResponseContentType.m_value \
            + ". It is not marked to be inspected.");
        std::string validContetTypes("");
        for (std::set<std::string>::iterator i = bi.begin();
             i != bi.end(); ++i) {
            validContetTypes.append(*i + " ");
        }
        ms_dbg(8, "Content-Type(s) marked to be inspected: " \
            + validContetTypes);
        return true;
    }
    if (m_variableOutboundDataError.m_value.empty() == true) {
        m_variableOutboundDataError.set("0", m_variableOffset);
    }

    m_variableResponseBody.set(m_responseBody.str(), m_variableOffset);
    m_variableResponseContentLength.set(std::to_string(
        m_responseBody.str().size()), m_variableOffset);

    m_rules->evaluate(modsecurity::ResponseBodyPhase, this);
    return true;
}


/**
 * @name    appendResponseBody
 * @brief   Adds reponse body to be inspected.
 *
 * With this method it is possible to feed ModSecurity with data for
 * inspection regarding the response body. ModSecurity can also update the
 * contents of the response body, this is not quite ready yet on this version
 * of the API. 
 *
 * @note If the content is updated, the client cannot receive the content
 *       length header filled, at least not with the old values. Otherwise
 *       unexpected behavior may happens.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed, process partial demanded.
 *
 */
int Transaction::appendResponseBody(const unsigned char *buf, size_t len) {
    int current_size = this->m_responseBody.tellp();

    std::set<std::string> &bi = \
        this->m_rules->m_responseBodyTypeToBeInspected.m_value;
    auto t = bi.find(m_variableResponseContentType.m_value);
    if (t == bi.end() && bi.empty() == false) {
        ms_dbg(4, "Not appending response body. " \
            "Response Content-Type is " \
            + m_variableResponseContentType.m_value \
            + ". It is not marked to be inspected.");
        return true;
    }

    ms_dbg(9, "Appending response body: " + std::to_string(len + current_size)
        + " bytes. Limit set to: " +
        std::to_string(this->m_rules->m_responseBodyLimit.m_value));

    if (this->m_rules->m_responseBodyLimit.m_value > 0
        && this->m_rules->m_responseBodyLimit.m_value < len + current_size) {
        m_variableOutboundDataError.set("1", m_variableOffset);
        ms_dbg(5, "Response body is bigger than the maximum expected.");
        if (this->m_rules->m_responseBodyLimitAction ==
            RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction) {
            size_t spaceLeft = this->m_rules->m_responseBodyLimit.m_value \
                - current_size;
            this->m_responseBody.write(reinterpret_cast<const char*>(buf),
                spaceLeft);
            ms_dbg(5, "Response body limit is marked to process partial");
            return false;
        } else {
            if (this->m_rules->m_responseBodyLimitAction ==
                RulesSet::BodyLimitAction::RejectBodyLimitAction) {
                ms_dbg(5, "Response body limit is marked to reject the " \
                    "request");
                if (getRuleEngineState() == RulesSet::EnabledRuleEngine) {
                    intervention::free(&m_it);
                    m_it.log = strdup("Response body limit is marked to reject " \
                        "the request");
                    m_it.status = 403;
                    m_it.disruptive = true;
                } else {
                    ms_dbg(5, "Not rejecting the request as the engine is " \
                        "not Enabled");
                }
            }
            return true;
        }
    }

    this->m_responseBody.write(reinterpret_cast<const char*>(buf), len);

    return true;
}


/**
 * @name    getResponseBody
 * @brief   Retrieve a buffer with the updated response body.
 *
 * This method is needed to be called whenever ModSecurity update the
 * contents of the response body, otherwise there is no need to call this
 * method.
 *
 * WARN: This is a skeleton that it is not in use yet.
 *
 * @return It returns a buffer (const char *)
 *
 */
const char *Transaction::getResponseBody() const {
    return strdup(this->m_responseBody.str().c_str());
}


/**
 * @name    getResponseBodyLength
 * @brief   Retrieve the length of the response body.
 *
 * This method returns the size of the response body buffer.
 *
 *
 * @return Size of the update response body.
 *
 */
size_t Transaction::getResponseBodyLength() {
    size_t size = 0;
    m_responseBody.seekp(0, std::ios::end);
    size = m_responseBody.tellp();

    return size;
}

/**
 * @name    getRequestBodyLength
 * @brief   Retrieve the length of the request body.
 *
 * This method returns the size of the request body buffer, notice
 * however, that most likely there isn't an update. Thus, this method will
 * return 0.
 *
 *
 * @return Size of the request body.
 *
 */
size_t Transaction::getRequestBodyLength() {
    size_t size = 0;

    m_requestBody.seekp(0, std::ios::end);
    size = m_requestBody.tellp();

    return size;
}


/**
 * @name    processLogging
 * @brief   Logging all information relative to this transaction.
 *
 * At this point there is not need to hold the connection, the response can be
 * delivered prior to the execution of this method.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::processLogging() {
    ms_dbg(4, "Starting phase LOGGING. (SecRules 5)");

    if (getRuleEngineState() == RulesSet::DisabledRuleEngine) {
        ms_dbg(4, "Rule engine disabled, returning...");
        return true;
    }

    this->m_rules->evaluate(modsecurity::LoggingPhase, this);

    /* If relevant, save this transaction information at the audit_logs */
    if (m_rules != NULL && m_rules->m_auditLog != NULL) {
        int parts = this->m_rules->m_auditLog->getParts();
        ms_dbg(8, "Checking if this request is suitable to be " \
            "saved as an audit log.");

        if (!this->m_auditLogModifier.empty()) {
            ms_dbg(4, "There was an audit log modifier for this transaction.");
            std::list<std::pair<int, std::string>>::iterator it;
            ms_dbg(7, "AuditLog parts before modification(s): " +
                std::to_string(parts) + ".");
            for (it = m_auditLogModifier.begin();
                it != m_auditLogModifier.end(); ++it) {
                std::pair <int, std::string> p = *it;
                if (p.first == 0) {  // Add
                    parts = this->m_rules->m_auditLog->addParts(parts,
                        p.second);
                } else {  // Remove
                    parts = this->m_rules->m_auditLog->removeParts(parts,
                        p.second);
                }
            }
        }
        ms_dbg(8, "Checking if this request is relevant to be " \
            "part of the audit logs.");
        bool saved = this->m_rules->m_auditLog->saveIfRelevant(this, parts);
        if (saved) {
            ms_dbg(8, "Request was relevant to be saved. Parts: " +
                std::to_string(parts));
        }
    }

    return true;
}


/**
 * @name    intervention
 * @brief   Check if ModSecurity has anything to ask to the server.
 *
 * Intervention can generate a log event and/or perform a disruptive action.
 *
 * @param Pointer ModSecurityIntervention structure
 * @retval true  A intervention should be made.
 * @retval false Nothing to be done.
 *
 */
bool Transaction::intervention(ModSecurityIntervention *it) {
    if (m_it.disruptive) {
        if (m_it.url) {
            it->url = strdup(m_it.url);
        }
        it->disruptive = m_it.disruptive;
        it->status = m_it.status;

        if (m_it.log != NULL) {
            std::string log("");
            log.append(m_it.log);
            utils::string::replaceAll(&log, std::string("%d"),
                std::to_string(it->status));
            it->log = strdup(log.c_str());
        }
        intervention::reset(&m_it);
    }

    return it->disruptive;
}


std::string Transaction::toOldAuditLogFormatIndex(const std::string &filename,
    double size, const std::string &md5) {
    std::stringstream ss;
    struct tm timeinfo;
    char tstr[300];

    memset(tstr, '\0', 300);
    localtime_r(&this->m_timeStamp, &timeinfo);

    strftime(tstr, 299, "[%d/%b/%Y:%H:%M:%S %z]", &timeinfo);

    ss << utils::string::dash_if_empty(
       m_variableRequestHeaders.resolveFirst("Host").get())
        << " ";
    ss << utils::string::dash_if_empty(this->m_clientIpAddress->c_str()) << " ";
    /** TODO: Check variable */
    variables::RemoteUser *r = new variables::RemoteUser("REMOTE_USER");
    std::vector<const VariableValue *> l;
    r->evaluate(this, NULL, &l);
    for (auto &a : l) {
        delete a;
    }
    delete r;

    ss << utils::string::dash_if_empty(
        m_variableRemoteUser.c_str());
    ss << " ";
    /** TODO: Check variable */
    //ss << utils::string::dash_if_empty(
    //    this->m_collections.resolveFirst("LOCAL_USER").get());
    //ss << " ";
    ss << tstr << " ";

    ss << "\"";
    ss << utils::string::dash_if_empty(m_variableRequestMethod.evaluate());
    ss << " ";
    ss << this->m_uri.c_str() << " ";
    ss << "HTTP/" << m_httpVersion.c_str();
    ss << "\" ";

    ss << this->m_httpCodeReturned << " ";
    ss << this->m_responseBody.tellp() << " ";
    /** TODO: Check variable */
    ss << utils::string::dash_if_empty(
        m_variableRequestHeaders.resolveFirst("REFERER").get()) << " ";
    ss << "\"";
    ss << utils::string::dash_if_empty(
        m_variableRequestHeaders.resolveFirst("User-Agent").get());
    ss << "\" ";
    ss << *m_id.get() << " ";
    /** TODO: Check variable */
    ss << utils::string::dash_if_empty(
        m_variableRequestHeaders.resolveFirst("REFERER").get()) << " ";

    ss << filename << " ";
    ss << "0" << " ";
    ss << std::to_string(size) << " ";
    ss << "md5:" << md5 << std::endl;

    return ss.str();
}


std::string Transaction::toOldAuditLogFormat(int parts,
    const std::string &trailer) {
    std::stringstream audit_log;
    struct tm timeinfo;
    char tstr[300];

    memset(tstr, '\0', 300);
    localtime_r(&this->m_timeStamp, &timeinfo);

    audit_log << "--" << trailer << "-" << "A--" << std::endl;
    strftime(tstr, 299, "[%d/%b/%Y:%H:%M:%S %z]", &timeinfo);
    audit_log << tstr;
    audit_log << " " << m_id->c_str();
    audit_log << " " << this->m_clientIpAddress->c_str();
    audit_log << " " << this->m_clientPort;
    audit_log << " " << m_serverIpAddress->c_str();
    audit_log << " " << this->m_serverPort;
    audit_log << std::endl;

    if (parts & audit_log::AuditLog::BAuditLogPart) {
        std::vector<const VariableValue *> l;
        audit_log << "--" << trailer << "-" << "B--" << std::endl;
        audit_log << utils::string::dash_if_empty(
            m_variableRequestMethod.evaluate());
        audit_log << " " << this->m_uri.c_str() << " " << "HTTP/";
        audit_log << this->m_httpVersion.c_str() << std::endl;

        m_variableRequestHeaders.resolve(&l);
        for (auto &h : l) {
            size_t pos = strlen("REQUEST_HEADERS:");
            audit_log << h->getKeyWithCollection().c_str() + pos << ": ";
            audit_log << h->getValue().c_str() << std::endl;
            delete h;
        }
        audit_log << std::endl;
    }
    if (parts & audit_log::AuditLog::CAuditLogPart
        &&  m_requestBody.tellp() > 0) {
        std::string body =  m_requestBody.str();
        audit_log << "--" << trailer << "-" << "C--" << std::endl;
        if (body.size() > 0) {
            audit_log << body << std::endl;
        }
        audit_log << std::endl;
    }
    if (parts & audit_log::AuditLog::DAuditLogPart) {
        audit_log << "--" << trailer << "-" << "D--" << std::endl;
        audit_log << std::endl;
        /** TODO: write audit_log D part. */
    }
    if (parts & audit_log::AuditLog::EAuditLogPart
        && m_responseBody.tellp() > 0) {
        std::string body = utils::string::toHexIfNeeded(m_responseBody.str());
        audit_log << "--" << trailer << "-" << "E--" << std::endl;
        if (body.size() > 0) {
            audit_log << body << std::endl;
        }
        audit_log << std::endl;
    }
    if (parts & audit_log::AuditLog::FAuditLogPart) {
        std::vector<const VariableValue *> l;

        audit_log << "--" << trailer << "-" << "F--" << std::endl;
        audit_log << "HTTP/" << m_httpVersion.c_str()  << " ";
        audit_log << this->m_httpCodeReturned << std::endl;
        m_variableResponseHeaders.resolve(&l);
        for (auto &h : l) {
            audit_log << h->getKey().c_str() << ": ";
            audit_log << h->getValue().c_str() << std::endl;
            delete h;
        }
    }
    audit_log << std::endl;

    if (parts & audit_log::AuditLog::GAuditLogPart) {
        audit_log << "--" << trailer << "-" << "G--" << std::endl;
        audit_log << std::endl;
        /** TODO: write audit_log G part. */
    }
    if (parts & audit_log::AuditLog::HAuditLogPart) {
        audit_log << "--" << trailer << "-" << "H--" << std::endl;
        for (auto a : m_rulesMessages) {
            audit_log << a.log(0, m_httpCodeReturned) << std::endl;
        }
        audit_log << std::endl;
        /** TODO: write audit_log H part. */
    }
    if (parts & audit_log::AuditLog::IAuditLogPart) {
        audit_log << "--" << trailer << "-" << "I--" << std::endl;
        audit_log << std::endl;
        /** TODO: write audit_log I part. */
    }
    if (parts & audit_log::AuditLog::JAuditLogPart) {
        audit_log << "--" << trailer << "-" << "J--" << std::endl;
        audit_log << std::endl;
        /** TODO: write audit_log J part. */
    }
    if (parts & audit_log::AuditLog::KAuditLogPart) {
        audit_log << "--" << trailer << "-" << "K--" << std::endl;
        audit_log << std::endl;
        /** TODO: write audit_log K part. */
    }
    audit_log << "--" << trailer << "-" << "Z--" << std::endl << std::endl;

    return audit_log.str();
}


std::string Transaction::toJSON(int parts) {
#ifdef WITH_YAJL
    const unsigned char *buf;
    size_t len;
    yajl_gen g;
    std::string log;
    std::string ts = utils::string::ascTime(&m_timeStamp).c_str();
    std::string uniqueId = UniqueId::uniqueId();

    g = yajl_gen_alloc(NULL);
    if (g == NULL) {
      return "";
    }
    yajl_gen_config(g, yajl_gen_beautify, 0);

    /* main */
    yajl_gen_map_open(g);

    /* trasaction */
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>("transaction"),
        strlen("transaction"));

    yajl_gen_map_open(g);
    /* Part: A (header mandatory) */
    LOGFY_ADD("client_ip", this->m_clientIpAddress->c_str());
    LOGFY_ADD("time_stamp", ts.c_str());
    LOGFY_ADD("server_id", uniqueId.c_str());
    LOGFY_ADD_NUM("client_port", m_clientPort);
    LOGFY_ADD("host_ip", m_serverIpAddress->c_str());
    LOGFY_ADD_NUM("host_port", m_serverPort);
    LOGFY_ADD("unique_id", m_id->c_str());

    /* request */
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>("request"),
        strlen("request"));
    yajl_gen_map_open(g);

    LOGFY_ADD("method",
        utils::string::dash_if_empty(
            m_variableRequestMethod.evaluate()).c_str());

    LOGFY_ADD_INT("http_version", m_httpVersion.c_str());
    LOGFY_ADD("uri", this->m_uri.c_str());

    if (parts & audit_log::AuditLog::CAuditLogPart) {
        // FIXME: check for the binary content size.
        LOGFY_ADD("body", this->m_requestBody.str().c_str());
    }

    /* request headers */
    if (parts & audit_log::AuditLog::BAuditLogPart) {
        std::vector<const VariableValue *> l;
        yajl_gen_string(g, reinterpret_cast<const unsigned char*>("headers"),
            strlen("headers"));
        yajl_gen_map_open(g);

        m_variableRequestHeaders.resolve(&l);
        for (auto &h : l) {
            LOGFY_ADD(h->getKey().c_str(), h->getValue().c_str());
            delete h;
        }

        /* end: request headers */
        yajl_gen_map_close(g);
    }

    /* end: request */
    yajl_gen_map_close(g);

    /* response */
    yajl_gen_string(g, reinterpret_cast<const unsigned char*>("response"),
        strlen("response"));
    yajl_gen_map_open(g);

    if (parts & audit_log::AuditLog::EAuditLogPart) {
        LOGFY_ADD("body", this->m_responseBody.str().c_str());
    }
    LOGFY_ADD_NUM("http_code", m_httpCodeReturned);

    /* response headers */
    if (parts & audit_log::AuditLog::FAuditLogPart) {
        std::vector<const VariableValue *> l;
        yajl_gen_string(g, reinterpret_cast<const unsigned char*>("headers"),
            strlen("headers"));
        yajl_gen_map_open(g);

        m_variableResponseHeaders.resolve(&l);
        for (auto &h : l) {
            LOGFY_ADD(h->getKey().c_str(), h->getValue().c_str());
            delete h;
        }

        /* end: response headers */
        yajl_gen_map_close(g);
    }
    /* end: response */
    yajl_gen_map_close(g);

    /* producer */
    if (parts & audit_log::AuditLog::HAuditLogPart) {
        yajl_gen_string(g, reinterpret_cast<const unsigned char*>("producer"),
            strlen("producer"));
        yajl_gen_map_open(g);

        /* producer > libmodsecurity */
        LOGFY_ADD("modsecurity", m_ms->whoAmI().c_str());

        /* producer > connector */
        LOGFY_ADD("connector", m_ms->getConnectorInformation().c_str());

        /* producer > engine state */
        LOGFY_ADD("secrules_engine",
            RulesSet::ruleEngineStateString(
            (RulesSetProperties::RuleEngine) getRuleEngineState()));

        /* producer > components */
        yajl_gen_string(g,
            reinterpret_cast<const unsigned char*>("components"),
            strlen("components"));

        yajl_gen_array_open(g);
        for (auto a : m_rules->m_components) {
            yajl_gen_string(g,
                reinterpret_cast<const unsigned char*>
                    (a.c_str()), a.length());
        }
        yajl_gen_array_close(g);

        /* end: producer */
        yajl_gen_map_close(g);

        /* messages */
        yajl_gen_string(g,
            reinterpret_cast<const unsigned char*>("messages"),
            strlen("messages"));
        yajl_gen_array_open(g);
        for (auto a : m_rulesMessages) {
            yajl_gen_map_open(g);
            LOGFY_ADD("message", a.m_message.c_str());
            yajl_gen_string(g,
                reinterpret_cast<const unsigned char*>("details"),
                strlen("details"));
            yajl_gen_map_open(g);
            LOGFY_ADD("match", a.m_match.c_str());
            LOGFY_ADD("reference", a.m_reference.c_str());
            LOGFY_ADD("ruleId", std::to_string(a.m_ruleId).c_str());
            LOGFY_ADD("file", a.m_ruleFile->c_str());
            LOGFY_ADD("lineNumber", std::to_string(a.m_ruleLine).c_str());
            LOGFY_ADD("data", a.m_data.c_str());
            LOGFY_ADD("severity", std::to_string(a.m_severity).c_str());
            LOGFY_ADD("ver", a.m_ver.c_str());
            LOGFY_ADD("rev", a.m_rev.c_str());

            yajl_gen_string(g,
                reinterpret_cast<const unsigned char*>("tags"),
                strlen("tags"));
            yajl_gen_array_open(g);
            for (auto b : a.m_tags) {
                yajl_gen_string(g,
                    reinterpret_cast<const unsigned char*>(b.c_str()),
                    strlen(b.c_str()));
            }
            yajl_gen_array_close(g);

            LOGFY_ADD("maturity", std::to_string(a.m_maturity).c_str());
            LOGFY_ADD("accuracy", std::to_string(a.m_accuracy).c_str());
            yajl_gen_map_close(g);
            yajl_gen_map_close(g);
        }
        yajl_gen_array_close(g);
        /* end: messages */
    }

    /* end: transaction */
    yajl_gen_map_close(g);

    /* end: main */
    yajl_gen_map_close(g);

    yajl_gen_get_buf(g, &buf, &len);

    log.assign(reinterpret_cast<const char*>(buf), len);
    log.append("\n");

    yajl_gen_free(g);

    return log;
#else
    return std::string("{\"error\":\"ModSecurity was " \
        "not compiled with JSON support.\"}");
#endif
}


void Transaction::serverLog(std::shared_ptr<RuleMessage> rm) {
    m_ms->serverLog(m_logCbData, rm);
}


int Transaction::getRuleEngineState() const {
    if (m_secRuleEngine == RulesSetProperties::PropertyNotSetRuleEngine) {
        return m_rules->m_secRuleEngine;
    }

    return m_secRuleEngine;
}


/**
 * @name    updateStatusCode
 * @brief   Updates response status code.
 *
 * Called after processResponseHeaders to inform a new response code.
 * Not mandatory.
 *
 *
 * @param status The returned http code.
 *
 * @returns If the operation was successful or not.
 * @retval true Operation was successful.
 * @retval false Operation failed.
 *
 */
int Transaction::updateStatusCode(int code) {
    this->m_httpCodeReturned = code;
    m_variableResponseStatus.set(std::to_string(code), m_variableOffset);

    return true;
}


/**
 * @name    msc_new_transaction
 * @brief   Create a new transaction for a given configuration and ModSecurity core.
 *
 * The transaction is the unit that will be used the inspect every request. It holds
 * all the information for a given request.
 * 
 * @note Remember to cleanup the transaction when the transaction is complete.
 *
 * @param ms ModSecurity core pointer.
 * @param rules Rules pointer.
 *
 * @return Pointer to Transaction structure
 * @retval >0   Transaction structure was initialized correctly
 * @retval NULL Transaction cannot be initialized, either by problems with the rules,
 *              problems with the ModSecurity core or missing memory to
 *              allocate the resources needed by the transaction.
 *
 */
extern "C" Transaction *msc_new_transaction(ModSecurity *ms,
    RulesSet *rules, void *logCbData) {
    return new Transaction(ms, rules, logCbData);
}
extern "C" Transaction *msc_new_transaction_with_id(ModSecurity *ms,
    RulesSet *rules, char *id, void *logCbData) {
    return new Transaction(ms, rules, id, logCbData);
}

/**
 * @name    msc_process_connection
 * @brief   Perform the analysis on the connection.
 *
 * This function should be called at very beginning of a request process, it is
 * expected to be executed prior to the virtual host resolution, when the
 * connection arrives on the server.
 *
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 * @param client Client's IP address in text format.
 * @param cPort Client's port
 * @param server Server's IP address in text format.
 * @param sPort Server's port
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_connection(Transaction *transaction,
    const char *client, int cPort, const char *server, int sPort) {
    return transaction->processConnection(client, cPort, server, sPort);
}


/**
 * @name    msc_process_uri
 * @brief   Perform the analysis on the URI and all the query string variables.
 *
 * This function should be called at very beginning of a request process, it is
 * expected to be executed prior to the virtual host resolution, when the
 * connection arrives on the server.
 *
 * @note There is no direct connection between this function and any phase of
 *       the SecLanguage's phases. It is something that may occur between the
 *       SecLanguage phase 1 and 2.
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 * @param uri   Uri.
 * @param protocol   Protocol (GET, POST, PUT).
 * @param http_version   Http version (1.0, 1.2, 2.0).
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_uri(Transaction *transaction, const char *uri,
    const char *protocol, const char *http_version) {
    return transaction->processURI(uri, protocol, http_version);
}


/**
 * @name    msc_process_request_headers
 * @brief   Perform the analysis on the request readers.
 *
 * This function perform the analysis on the request headers, notice however
 * that the headers should be added prior to the execution of this function.
 *
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_request_headers(Transaction *transaction) {
    return transaction->processRequestHeaders();
}


/**
 * @name    msc_process_request_body
 * @brief   Perform the analysis on the request body (if any)
 *
 * This function perform the analysis on the request body. It is optional to
 * call that function. If this API consumer already know that there isn't a
 * body for inspect it is recommended to skip this step.
 *
 * @note It is necessary to "append" the request body prior to the execution
 *       of this function.
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 * 
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_request_body(Transaction *transaction) {
    return transaction->processRequestBody();
}


/**
 * @name    msc_append_request_body
 * @brief   Adds request body to be inspected.
 *
 * With this function it is possible to feed ModSecurity with data for
 * inspection regarding the request body. There are two possibilities here:
 * 
 * 1 - Adds the buffer in a row;
 * 2 - Adds it in chunks;
 *
 * A third option should be developed which is share your application buffer.
 * In any case, remember that the utilization of this function may reduce your
 * server throughput, as this buffer creations is computationally expensive.
 *
 * @note While feeding ModSecurity remember to keep checking if there is an
 *       intervention, Sec Language has the capability to set the maximum
 *       inspection size which may be reached, and the decision on what to do
 *       in this case is upon the rules.
 *
 * @param transaction ModSecurity transaction.
 * 
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_append_request_body(Transaction *transaction,
    const unsigned char *buf, size_t len) {
    return transaction->appendRequestBody(buf, len);
}


extern "C" int msc_request_body_from_file(Transaction *transaction,
    const char *path) {
    return transaction->requestBodyFromFile(path);
}


/**
 * @name    msc_process_response_headers
 * @brief   Perform the analysis on the response headers.
 *
 * This function perform the analysis on the response headers, notice however
 * that the headers should be added prior to the execution of this function.
 *
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_response_headers(Transaction *transaction,
    int code, const char* protocol) {
    return transaction->processResponseHeaders(code, protocol);
}


/**
 * @name    msc_process_response_body
 * @brief   Perform the analysis on the response body (if any)
 *
 * This function perform the analysis on the response body. It is optional to
 * call that function. If this API consumer already know that there isn't a
 * body for inspect it is recommended to skip this step.
 *
 * @note It is necessary to "append" the response body prior to the execution
 *       of this function.
 * @note Remember to check for a possible intervention.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_response_body(Transaction *transaction) {
    return transaction->processResponseBody();
}


/**
 * @name    msc_append_response_body
 * @brief   Adds reponse body to be inspected.
 *
 * With this function it is possible to feed ModSecurity with data for
 * inspection regarding the response body. ModSecurity can also update the
 * contents of the response body, this is not quite ready yet on this version
 * of the API. 
 *
 * @note If the content is updated, the client cannot receive the content
 *       length header filled, at least not with the old values. Otherwise
 *       unexpected behavior may happens.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_append_response_body(Transaction *transaction,
    const unsigned char *buf, size_t len) {
    return transaction->appendResponseBody(buf, len);
}


/**
 * @name    msc_add_request_header
 * @brief   Adds a request header
 *
 * With this function it is possible to feed ModSecurity with a request header.
 *
 * @note This function expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param transaction ModSecurity transaction.
 * @param key   header name.
 * @param value header value.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_add_request_header(Transaction *transaction,
    const unsigned char *key,
    const unsigned char *value) {
    return transaction->addRequestHeader(key, value);
}


/**
 * @name    msc_add_n_request_header
 * @brief   Adds a request header
 *
 * Same as msc_add_request_header, do not expect a NULL terminated string,
 * instead it expect the string and the string size, for the value and key.
 *
 * @param transaction   ModSecurity transaction.
 * @param key     header name.
 * @param key_len header name size.
 * @param value   header value.
 * @param val_len header value size.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_add_n_request_header(Transaction *transaction,
    const unsigned char *key,
    size_t key_len, const unsigned char *value, size_t value_len) {
    return transaction->addRequestHeader(key, key_len, value, value_len);
}


/**
 * @name    msc_add_response_header
 * @brief   Adds a response header
 *
 * With this function it is possible to feed ModSecurity with a response
 * header.
 *
 * @note This function expects a NULL terminated string, for both: key and
 *       value.
 *
 * @param transaction   ModSecurity transaction.
 * @param key     header name.
 * @param value   header value.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_add_response_header(Transaction *transaction,
    const unsigned char *key,
    const unsigned char *value) {
    return transaction->addResponseHeader(key, value);
}


/**
 * @name    msc_add_n_response_header
 * @brief   Adds a response header
 *
 * Same as msc_add_response_header, do not expect a NULL terminated string,
 * instead it expect the string and the string size, for the value and key.
 *
 * @param transaction   ModSecurity transaction.
 * @param key     header name.
 * @param key_len header name size.
 * @param value   header value.
 * @param val_len header value size.
 * 
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_add_n_response_header(Transaction *transaction,
    const unsigned char *key, size_t key_len, const unsigned char *value,
    size_t value_len) {
    return transaction->addResponseHeader(key, key_len, value, value_len);
}


/**
 * @name    msc_transaction_cleanup
 * @brief   Removes all the resources allocated by a given Transaction.
 *
 * It is mandatory to call this function after every request being finished,
 * otherwise it may end up in a huge memory leak.
 *
 * @param transaction ModSecurity transaction.
 *
 */
extern "C" void msc_transaction_cleanup(Transaction *transaction) {
    delete transaction;
}


/**
 * @name    msc_intervention
 * @brief   Check if ModSecurity has anything to ask to the server.
 *
 * Intervention can generate a log event and/or perform a disruptive action.
 *
 * @param transaction ModSecurity transaction.
 *
 * @return Pointer to ModSecurityIntervention structure
 * @retval >0   A intervention should be made.
 * @retval NULL Nothing to be done.
 *
 */
extern "C" int msc_intervention(Transaction *transaction,
    ModSecurityIntervention *it) {
    return transaction->intervention(it);
}


/**
 * @name    msc_get_response_body
 * @brief   Retrieve a buffer with the updated response body.
 *
 * This function is needed to be called whenever ModSecurity update the
 * contents of the response body, otherwise there is no need to call this
 * function.
 *
 * @param transaction ModSecurity transaction.
 *
 * @return It returns a buffer (const char *)
 * @retval >0   body was update and available.
 * @retval NULL Nothing was updated.
 *
 */
extern "C" const char *msc_get_response_body(Transaction *transaction) {
    return transaction->getResponseBody();
}


/**
 * @name    msc_get_response_body_length
 * @brief   Retrieve the length of the response body.
 *
 * This function returns the size of the response body buffer.
 *
 * @param transaction ModSecurity transaction.
 *
 * @return Size of the response body.
 *
 */
extern "C" size_t msc_get_response_body_length(Transaction *transaction) {
    return transaction->getResponseBodyLength();
}

/**
 * @name    msc_get_request_body_length
 * @brief   Retrieve the length of the request body.
 *
 * This function returns the size of the request body buffer.
 *
 * @param transaction ModSecurity transaction.
 *
 * @return Size of the request body.
 *
 */
extern "C" size_t msc_get_request_body_length(Transaction *transaction) {
    return transaction->getRequestBodyLength();
}

/**
 * @name    msc_process_logging
 * @brief   Logging all information relative to this transaction.
 *
 * At this point there is not need to hold the connection, the response can be
 * delivered prior to the execution of this function.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_process_logging(Transaction *transaction) {
    return transaction->processLogging();
}


/**
 * @name    msc_update_status_code
 * @brief   Updates response status code.
 *
 * Called after msc_process_response_headers to inform a new response code.
 * Not mandatory.
 *
 * @param transaction ModSecurity transaction.
 *
 * @returns If the operation was successful or not.
 * @retval 1 Operation was successful.
 * @retval 0 Operation failed.
 *
 */
extern "C" int msc_update_status_code(Transaction *transaction, int status) {
    return transaction->updateStatusCode(status);
}


}  // namespace modsecurity

