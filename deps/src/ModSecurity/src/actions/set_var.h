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

#include <memory>
#include <string>
#include <utility>

#include "modsecurity/actions/action.h"
#include "src/run_time_string.h"

#ifndef SRC_ACTIONS_SET_VAR_H_
#define SRC_ACTIONS_SET_VAR_H_

namespace modsecurity {
class Transaction;
class Rule;

namespace actions {

enum SetVarOperation {
    /* Set variable to something */
    setOperation,
    /* read variable, sum predicate and set */
    sumAndSetOperation,
    /* read variable, substract predicate and set */
    substractAndSetOperation,
    /* set variable to 1 */
    setToOneOperation,
    /* unset operation */
    unsetOperation,
};

class SetVar : public Action {
 public:
    SetVar(SetVarOperation operation,
        std::unique_ptr<modsecurity::variables::Variable> variable,
        std::unique_ptr<RunTimeString> predicate)
        : Action("setvar"),
        m_operation(operation),
        m_variable(std::move(variable)),
        m_string(std::move(predicate)) { }

    SetVar(SetVarOperation operation,
        std::unique_ptr<modsecurity::variables::Variable> variable)
        : Action("setvar"),
        m_operation(operation),
        m_variable(std::move(variable)) { }

    bool evaluate(Rule *rule, Transaction *transaction) override;
    bool init(std::string *error) override;

 private:
    SetVarOperation m_operation;
    std::unique_ptr<modsecurity::variables::Variable> m_variable;
    std::unique_ptr<RunTimeString> m_string;
};

}  // namespace actions
}  // namespace modsecurity


#endif  // SRC_ACTIONS_SET_VAR_H_
