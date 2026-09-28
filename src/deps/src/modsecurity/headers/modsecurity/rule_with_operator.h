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
#include <memory>
#include <utility>
#endif

#ifndef HEADERS_MODSECURITY_RULE_WITH_OPERATOR_H_
#define HEADERS_MODSECURITY_RULE_WITH_OPERATOR_H_

#include "modsecurity/transaction.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/variable_value.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_with_actions.h"

#ifdef __cplusplus

namespace modsecurity {


class RuleWithOperator : public RuleWithActions {
 public:
    RuleWithOperator(operators::Operator *op,
        variables::Variables *variables,
        std::vector<actions::Action *> *actions,
        Transformations *transformations,
        const std::string &fileName,
        int lineNumber);

    ~RuleWithOperator() override;

    bool evaluate(Transaction *transaction, RuleMessage &ruleMessage) override;

    void getVariablesExceptions(Transaction &t,
        variables::Variables *exclusion, variables::Variables *addition);
    inline void getFinalVars(variables::Variables *vars,
        variables::Variables *eclusion, Transaction *trans);

    bool executeOperatorAt(Transaction *trasn, const std::string &key,
        const std::string &value, RuleMessage &ruleMessage);

    static void updateMatchedVars(Transaction *trasn, const std::string &key,
        const std::string &value);


    const std::string& getOperatorName() const;

    virtual std::string getReference() override {
        return std::to_string(m_ruleId);
    }

 private:
    modsecurity::variables::Variables *m_variables;
    operators::Operator *m_operator;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_WITH_OPERATOR_H_
