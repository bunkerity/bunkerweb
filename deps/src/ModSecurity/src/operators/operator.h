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

#include <string>
#include <memory>
#include <utility>

#ifndef SRC_OPERATORS_OPERATOR_H__
#define SRC_OPERATORS_OPERATOR_H__

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_message.h"
#include "src/run_time_string.h"

namespace modsecurity {
namespace operators {

class Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    Operator()
        : m_match_message(""),
        m_negation(false),
        m_op(""),
        m_param(""),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    Operator(std::string opName, std::string param, bool negation)
        : m_match_message(""),
        m_negation(negation),
        m_op(opName),
        m_param(param),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    Operator(std::string opName, std::unique_ptr<RunTimeString> param,
        bool negation)
        : m_match_message(""),
        m_negation(negation),
        m_op(opName),
        m_param(""),
        m_string(std::move(param)),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    Operator(std::string opName, std::string param)
        : m_match_message(""),
        m_negation(false),
        m_op(opName),
        m_param(param),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    Operator(std::string opName, std::unique_ptr<RunTimeString> param)
        : m_match_message(""),
        m_negation(false),
        m_op(opName),
        m_param(""),
        m_string(std::move(param)),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    explicit Operator(std::string opName)
        : m_match_message(""),
        m_negation(false),
        m_op(opName),
        m_param(),
        m_couldContainsMacro(false) {
            if (m_couldContainsMacro == false && m_string) {
                m_param = m_string->evaluate();
            }
        }

    virtual ~Operator() { }
    static Operator *instantiate(std::string opName, std::string param);

    virtual bool init(const std::string &arg, std::string *error) {
        return true;
    }

    virtual std::string resolveMatchMessage(Transaction *t,
        std::string key, std::string value);

    bool evaluateInternal(Transaction *t, const std::string& a);
    bool evaluateInternal(Transaction *t, Rule *rule,
        const std::string& a);
    bool evaluateInternal(Transaction *t, Rule *rule,
        const std::string& a, std::shared_ptr<RuleMessage> ruleMessage);


    virtual bool evaluate(Transaction *transaction, const std::string &str);
    virtual bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &str) {
        return evaluate(transaction, str);
    }
    virtual bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &str, std::shared_ptr<RuleMessage> ruleMessage) {
        return evaluate(transaction, str);
    }

    static void logOffset(std::shared_ptr<RuleMessage> ruleMessage,
        int offset, int len) {
        if (ruleMessage) {
            ruleMessage->m_reference.append("o"
                + std::to_string(offset) + ","
                + std::to_string(len));
        }
    }

    std::string m_match_message;
    bool m_negation;
    std::string m_op;
    std::string m_param;
    std::unique_ptr<RunTimeString> m_string;
    bool m_couldContainsMacro;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_OPERATOR_H__
