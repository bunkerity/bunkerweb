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

#ifndef HEADERS_MODSECURITY_ACTIONS_ACTION_H_
#define HEADERS_MODSECURITY_ACTIONS_ACTION_H_

#ifdef __cplusplus

#include <string>
#include <memory>

namespace modsecurity {
class Transaction;
class RuleWithOperator;
class RuleWithActions;
class RuleMessage;

namespace actions {


class Action {
 public:
    /**
     *
     * Define the action kind regarding to the execution time.
     * 
     * 
     */
    enum class Kind {
    /**
     *
     * Action that are executed while loading the configuration. For instance
     * the rule ID or the rule phase.
     *
     */
     ConfigurationKind,
    /**
     *
     * Those are actions that demands to be executed before call the operator.
     * For instance the tranformations.
     *
     *
     */
     RunTimeBeforeMatchAttemptKind,
    /**
     *
     * Actions that are executed after the execution of the operator, only if
     * the operator returned Match (or True). For instance the disruptive
     * actions.
     *
     */
     RunTimeOnlyIfMatchKind,
    };

    explicit Action(const std::string& _action)
        : m_isNone(false),
        temporaryAction(false),
        action_kind(Kind::RunTimeOnlyIfMatchKind),
        m_name(nullptr),
        m_parser_payload("") {
            set_name_and_payload(_action);
        }
    explicit Action(const std::string& _action, Kind kind)
        : m_isNone(false),
        temporaryAction(false),
        action_kind(kind),
        m_name(nullptr),
        m_parser_payload("") {
            set_name_and_payload(_action);
        }

    Action(const Action &a) = delete;

    Action &operator=(const Action& a) = delete;

    virtual ~Action() { }

    virtual bool evaluate(RuleWithActions *rule, Transaction *transaction);
    virtual bool evaluate(RuleWithActions *rule, Transaction *transaction,
        RuleMessage &ruleMessage) {
        return evaluate(rule, transaction);
    }
    virtual bool init(std::string *error) { return true; }
    virtual bool isDisruptive() { return false; }


    void set_name_and_payload(const std::string& data) {
        size_t pos = data.find(":");
        const char t[] = "t:";

        if (data.compare(0, std::size(t) - 1, t) == 0) {
            pos = data.find(":", 2);
        }

        if (pos == std::string::npos) {
            m_name = std::make_shared<std::string>(data);
            return;
        }

        m_name = std::make_shared<std::string>(data, 0, pos);
        m_parser_payload = std::string(data, pos + 1, data.length());

        if (m_parser_payload.at(0) == '\'' && m_parser_payload.size() > 2) {
            m_parser_payload.erase(0, 1);
            m_parser_payload.pop_back();
        }
    }

    bool m_isNone;
    bool temporaryAction;
    Kind action_kind;
    std::shared_ptr<std::string> m_name;
    std::string m_parser_payload;
 };


}  // namespace actions
}  // namespace modsecurity

#endif

#endif  // HEADERS_MODSECURITY_ACTIONS_ACTION_H_
