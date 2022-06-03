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
#include <memory>
#include <utility>
#endif

#ifndef HEADERS_MODSECURITY_RULE_H_
#define HEADERS_MODSECURITY_RULE_H_

#include "modsecurity/transaction.h"
#include "modsecurity/variable_value.h"


#ifdef __cplusplus

namespace modsecurity {
namespace variables {
class Variable;
class Variables;
}
namespace actions {
class Action;
class Severity;
class LogData;
class Msg;
class Rev;
class SetVar;
class Tag;
}
namespace operators {
class Operator;
}

class Rule {
 public:
    Rule(operators::Operator *_op,
            variables::Variables *_variables,
            std::vector<actions::Action *> *_actions,
            std::string fileName,
            int lineNumber);
    explicit Rule(std::string marker);
    virtual ~Rule();

    virtual bool evaluate(Transaction *transaction,
        std::shared_ptr<RuleMessage> rm);

    void organizeActions(std::vector<actions::Action *> *actions);
    void cleanUpActions();
    void executeAction(Transaction *trans,
    bool containsBlock, std::shared_ptr<RuleMessage> ruleMessage,
        actions::Action *a, bool context);

    inline void executeTransformation(actions::Action *a,
        std::shared_ptr<std::string> *value,
        Transaction *trans,
        std::list<std::pair<std::shared_ptr<std::string>,
        std::shared_ptr<std::string>>> *ret,
        std::string *path,
        int *nth);

    void getVariablesExceptions(Transaction *t,
        variables::Variables *exclusion, variables::Variables *addition);
    inline void getFinalVars(variables::Variables *vars,
        variables::Variables *eclusion, Transaction *trans);
    void executeActionsAfterFullMatch(Transaction *trasn,
        bool containsDisruptive, std::shared_ptr<RuleMessage> ruleMessage);

    std::list<std::pair<std::shared_ptr<std::string>,
        std::shared_ptr<std::string>>> executeDefaultTransformations(
        Transaction *trasn, const std::string &value);

    bool executeOperatorAt(Transaction *trasn, std::string key,
        std::string value, std::shared_ptr<RuleMessage> rm);
    void executeActionsIndependentOfChainedRuleResult(Transaction *trasn,
        bool *b, std::shared_ptr<RuleMessage> ruleMessage);
    inline void updateMatchedVars(Transaction *trasn, const std::string &key,
        const std::string &value);
    inline void cleanMatchedVars(Transaction *trasn);

    std::vector<actions::Action *> getActionsByName(const std::string& name,
        Transaction *t);
    bool containsTag(const std::string& name, Transaction *t);
    bool containsMsg(const std::string& name, Transaction *t);

    int refCountDecreaseAndCheck() {
        m_referenceCount--;
        if (m_referenceCount == 0) {
            delete this;
            return 1;
        }
        return 0;
    }


    void refCountIncrease() {
        m_referenceCount++;
    }

    void executeTransformations(
        actions::Action *a,
        std::shared_ptr<std::string> newValue,
        std::shared_ptr<std::string> value,
        Transaction *trans,
        std::list<std::pair<std::shared_ptr<std::string>,
        std::shared_ptr<std::string>>> *ret,
        std::shared_ptr<std::string> transStr,
        int nth);

    actions::Action *m_theDisruptiveAction;
    actions::LogData *m_logData;
    actions::Msg *m_msg;
    actions::Severity *m_severity;
    bool m_chained;
    bool m_containsCaptureAction;
    bool m_containsMultiMatchAction;
    bool m_containsStaticBlockAction;
    bool m_secMarker;
    int64_t m_ruleId;
    int m_accuracy;
    int m_lineNumber;
    int m_maturity;
    int m_phase;
    modsecurity::variables::Variables *m_variables;
    operators::Operator *m_op;
    Rule *m_chainedRuleChild;
    Rule *m_chainedRuleParent;
    std::string m_fileName;
    std::string m_marker;
    std::string m_rev;
    std::string m_ver;
    std::vector<actions::Action *> m_actionsRuntimePos;
    std::vector<actions::Action *> m_actionsRuntimePre;
    std::vector<actions::SetVar *> m_actionsSetVar;
    std::vector<actions::Tag *> m_actionsTag;
 private:
    bool m_unconditional;
    int m_referenceCount;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_H_
