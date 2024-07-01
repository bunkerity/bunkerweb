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
#include "modsecurity/rule_with_operator.h"


#ifdef __cplusplus

namespace modsecurity {



class RuleMessage {
 public:
    enum LogMessageInfo {
        ErrorLogTailLogMessageInfo = 2,
        ClientLogMessageInfo = 4
    };

    /**
     *
     * FIXME: RuleMessage is currently too big, doing a lot of
     * unnecessary data duplication. Needs to be shrink down.
     *
     */
    RuleMessage(RuleWithActions *rule, Transaction *trans) :
        m_accuracy(rule->m_accuracy),
        m_clientIpAddress(trans->m_clientIpAddress),
        m_data(""),
        m_id(trans->m_id),
        m_isDisruptive(false),
        m_match(""),
        m_maturity(rule->m_maturity),
        m_message(""),
        m_noAuditLog(false),
        m_phase(rule->getPhase() - 1),
        m_reference(""),
        m_rev(rule->m_rev),
        m_rule(rule),
        m_ruleFile(rule->getFileName()),
        m_ruleId(rule->m_ruleId),
        m_ruleLine(rule->getLineNumber()),
        m_saveMessage(true),
        m_serverIpAddress(trans->m_serverIpAddress),
        m_severity(0),
        m_uriNoQueryStringDecoded(trans->m_uri_no_query_string_decoded),
        m_ver(rule->m_ver),
        m_tags()
    { }

    explicit RuleMessage(RuleMessage *rule) :
        m_accuracy(rule->m_accuracy),
        m_clientIpAddress(rule->m_clientIpAddress),
        m_data(rule->m_data),
        m_id(rule->m_id),
        m_isDisruptive(rule->m_isDisruptive),
        m_match(rule->m_match),
        m_maturity(rule->m_maturity),
        m_message(rule->m_message),
        m_noAuditLog(rule->m_noAuditLog),
        m_phase(rule->m_phase),
        m_reference(rule->m_reference),
        m_rev(rule->m_rev),
        m_rule(rule->m_rule),
        m_ruleFile(rule->m_ruleFile),
        m_ruleId(rule->m_ruleId),
        m_ruleLine(rule->m_ruleLine),
        m_saveMessage(rule->m_saveMessage),
        m_serverIpAddress(rule->m_serverIpAddress),
        m_severity(rule->m_severity),
        m_uriNoQueryStringDecoded(rule->m_uriNoQueryStringDecoded),
        m_ver(rule->m_ver),
        m_tags(rule->m_tags)
    { }

    RuleMessage(const RuleMessage& ruleMessage)
        : m_accuracy(ruleMessage.m_accuracy),
        m_clientIpAddress(ruleMessage.m_clientIpAddress),
        m_data(ruleMessage.m_data),
        m_id(ruleMessage.m_id),
        m_isDisruptive(ruleMessage.m_isDisruptive),
        m_match(ruleMessage.m_match),
        m_maturity(ruleMessage.m_maturity),
        m_message(ruleMessage.m_message),
        m_noAuditLog(ruleMessage.m_noAuditLog),
        m_phase(ruleMessage.m_phase),
        m_reference(ruleMessage.m_reference),
        m_rev(ruleMessage.m_rev),
        m_rule(ruleMessage.m_rule),
        m_ruleFile(ruleMessage.m_ruleFile),
        m_ruleId(ruleMessage.m_ruleId),
        m_ruleLine(ruleMessage.m_ruleLine),
        m_saveMessage(ruleMessage.m_saveMessage),
        m_serverIpAddress(ruleMessage.m_serverIpAddress),
        m_severity(ruleMessage.m_severity),
        m_uriNoQueryStringDecoded(ruleMessage.m_uriNoQueryStringDecoded),
        m_ver(ruleMessage.m_ver),
        m_tags(ruleMessage.m_tags)
    { }

    RuleMessage &operator=(const RuleMessage& ruleMessage) {
        m_accuracy = ruleMessage.m_accuracy;
        m_clientIpAddress = ruleMessage.m_clientIpAddress;
        m_data = ruleMessage.m_data;
        m_id = ruleMessage.m_id;
        m_isDisruptive = ruleMessage.m_isDisruptive;
        m_match = ruleMessage.m_match;
        m_maturity = ruleMessage.m_maturity;
        m_message = ruleMessage.m_message;
        m_noAuditLog = ruleMessage.m_noAuditLog;
        m_phase = ruleMessage.m_phase;
        m_reference = ruleMessage.m_reference;
        m_rev = ruleMessage.m_rev;
        m_rule = ruleMessage.m_rule;
        m_ruleFile = ruleMessage.m_ruleFile;
        m_ruleId = ruleMessage.m_ruleId;
        m_ruleLine = ruleMessage.m_ruleLine;
        m_saveMessage = ruleMessage.m_saveMessage;
        m_serverIpAddress = ruleMessage.m_serverIpAddress;
        m_severity = ruleMessage.m_severity;
        m_uriNoQueryStringDecoded = ruleMessage.m_uriNoQueryStringDecoded;
        m_ver = ruleMessage.m_ver;
        m_tags = ruleMessage.m_tags;
        return *this;
    }

    void clean() {
        m_data = "";
        m_match = "";
        m_isDisruptive = false;
        m_reference = "";
        m_severity = 0;
        m_ver = "";
    }

    std::string log() {
        return log(this, 0);
    }
    std::string log(int props) {
        return log(this, props);
    }
    std::string log(int props, int responseCode) {
        return log(this, props, responseCode);
    }
    std::string errorLog() {
        return log(this,
		ClientLogMessageInfo | ErrorLogTailLogMessageInfo);
    }

    static std::string log(const RuleMessage *rm, int props, int code);
    static std::string log(const RuleMessage *rm, int props) {
        return log(rm, props, -1);
    }
    static std::string log(const RuleMessage *rm) {
        return log(rm, 0);
    }

    static std::string _details(const RuleMessage *rm);
    static std::string _errorLogTail(const RuleMessage *rm);

    int m_accuracy;
    std::shared_ptr<std::string> m_clientIpAddress;
    std::string m_data;
    std::shared_ptr<std::string> m_id;
    bool m_isDisruptive;
    std::string m_match;
    int m_maturity;
    std::string m_message;
    bool m_noAuditLog;
    int m_phase;
    std::string m_reference;
    std::string m_rev;
    RuleWithActions *m_rule;
    std::shared_ptr<std::string> m_ruleFile;
    int m_ruleId;
    int m_ruleLine;
    bool m_saveMessage;
    std::shared_ptr<std::string> m_serverIpAddress;
    int m_severity;
    std::shared_ptr<std::string> m_uriNoQueryStringDecoded;
    std::string m_ver;

    std::list<std::string> m_tags;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_MESSAGE_H_
