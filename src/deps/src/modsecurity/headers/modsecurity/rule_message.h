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

#ifndef HEADERS_MODSECURITY_RULE_MESSAGE_H_
#define HEADERS_MODSECURITY_RULE_MESSAGE_H_

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_with_operator.h"


#ifdef __cplusplus

#include <string>
#include <list>

namespace modsecurity {


class RuleMessage {
 public:
    enum LogMessageInfo {
        ErrorLogTailLogMessageInfo = 2,
        ClientLogMessageInfo = 4
    };

    RuleMessage(const RuleWithActions &rule, const Transaction &trans) :
        m_rule(rule),
        m_transaction(trans)
    {
        reset(true);
    }

    RuleMessage(const RuleMessage &ruleMessage) = default;
    RuleMessage &operator=(const RuleMessage &ruleMessage) = delete;

    void reset(const bool resetSaveMessage)
    {
        m_data.clear();
        m_isDisruptive = false;
        m_match.clear();
        m_message.clear();
        m_noAuditLog = false;
        m_reference.clear();
        if (resetSaveMessage == true)
            m_saveMessage = true;
        m_severity = 0;
        m_tags.clear();
    }

    std::string log() const {
        return log(*this, 0);
    }
    std::string log(int props) const {
        return log(*this, props);
    }
    std::string log(int props, int responseCode) const {
        return log(*this, props, responseCode);
    }
    std::string errorLog() const {
        return log(*this,
                   ClientLogMessageInfo | ErrorLogTailLogMessageInfo);
    }

    static std::string log(const RuleMessage &rm, int props, int code);
    static std::string log(const RuleMessage &rm, int props) {
        return log(rm, props, -1);
    }
    static std::string log(const RuleMessage &rm) {
        return log(rm, 0);
    }

    static std::string _details(const RuleMessage &rm);
    static std::string _errorLogTail(const RuleMessage &rm);

    int getPhase() const { return m_rule.getPhase() - 1; }

    const RuleWithActions &m_rule;
    const Transaction &m_transaction;
    std::string m_data;
    bool m_isDisruptive = false;
    std::string m_match;
    std::string m_message;
    bool m_noAuditLog = false;
    std::string m_reference;
    bool m_saveMessage = true;
    int m_severity = 0;

    std::list<std::string> m_tags;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_MESSAGE_H_
