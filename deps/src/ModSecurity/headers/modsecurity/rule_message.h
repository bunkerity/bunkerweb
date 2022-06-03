/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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
#include <stack>
#include <vector>
#include <string>
#include <list>
#include <cstring>
#endif

#ifndef HEADERS_MODSECURITY_RULE_MESSAGE_H_
#define HEADERS_MODSECURITY_RULE_MESSAGE_H_

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"


#ifdef __cplusplus

namespace modsecurity {



class RuleMessage {
 public:
    enum LogMessageInfo {
        ErrorLogTailLogMessageInfo = 2,
        ClientLogMessageInfo = 4
    };

    explicit RuleMessage(Rule *rule, Transaction *trans) :
        m_accuracy(rule->m_accuracy),
        m_clientIpAddress(trans->m_clientIpAddress),
        m_data(""),
        m_id(trans->m_id),
        m_isDisruptive(false),
        m_match(""),
        m_maturity(rule->m_maturity),
        m_message(""),
        m_noAuditLog(false),
        m_phase(rule->m_phase - 1),
        m_reference(""),
        m_rev(rule->m_rev),
        m_rule(rule),
        m_ruleFile(rule->m_fileName),
        m_ruleId(rule->m_ruleId),
        m_ruleLine(rule->m_lineNumber),
        m_saveMessage(true),
        m_serverIpAddress(trans->m_serverIpAddress),
        m_severity(0),
        m_uriNoQueryStringDecoded(trans->m_uri_no_query_string_decoded),
        m_ver(rule->m_ver)
    { }


    std::string log() {
        return RuleMessage::log(this, 0);
    }
    std::string log(int props) {
        return RuleMessage::log(this, props);
    }
    std::string log(int props, int responseCode) {
        return RuleMessage::log(this, props, responseCode);
    }
    std::string errorLog() {
        return RuleMessage::log(this,
		ClientLogMessageInfo | ErrorLogTailLogMessageInfo);
    }

    static std::string log(const RuleMessage *rm, int props, int code);
    static std::string log(const RuleMessage *rm, int props) {
        return RuleMessage::log(rm, props, -1);
    }
    static std::string log(const RuleMessage *rm) {
        return RuleMessage::log(rm, 0);
    }

    static std::string _details(const RuleMessage *rm);
    static std::string _errorLogTail(const RuleMessage *rm);

    int m_accuracy;
    std::string m_clientIpAddress;
    std::string m_data;
    std::string m_id;
    bool m_isDisruptive;
    std::string m_match;
    int m_maturity;
    std::string m_message;
    bool m_noAuditLog;
    int m_phase;
    std::string m_reference;
    std::string m_rev;
    Rule *m_rule;
    std::string m_ruleFile;
    int m_ruleId;
    int m_ruleLine;
    bool m_saveMessage;
    std::string m_serverIpAddress;
    int m_severity;
    std::string m_uriNoQueryStringDecoded;
    std::string m_ver;

    std::list<std::string> m_tags;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_MESSAGE_H_
