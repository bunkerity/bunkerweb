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

#include "modsecurity/rule_with_operator.h"

#include <stdio.h>

#include <algorithm>
#include <iostream>
#include <string>
#include <cstring>
#include <list>
#include <utility>
#include <memory>

#include "modsecurity/rules_set.h"
#include "src/operators/operator.h"
#include "modsecurity/actions/action.h"
#include "modsecurity/modsecurity.h"
#include "src/actions/transformations/none.h"
#include "src/actions/tag.h"
#include "src/utils/string.h"
#include "modsecurity/rule_message.h"
#include "src/actions/msg.h"
#include "src/actions/log_data.h"
#include "src/actions/severity.h"
#include "src/actions/capture.h"
#include "src/actions/multi_match.h"
#include "src/actions/set_var.h"
#include "src/actions/block.h"
#include "src/variables/variable.h"


namespace modsecurity {

using operators::Operator;
using actions::Action;
using variables::Variable;
using actions::transformations::None;


RuleWithOperator::RuleWithOperator(Operator *op,
    variables::Variables *_variables,
    std::vector<Action *> *actions,
    Transformations *transformations,
    const std::string &fileName,
    int lineNumber)
    : RuleWithActions(actions, transformations, fileName, lineNumber),
    m_variables(_variables),
    m_operator(op) { /* */ }


RuleWithOperator::~RuleWithOperator() {
    if (m_operator != NULL) {
        delete m_operator;
    }

    while (m_variables != NULL && m_variables->empty() == false) {
        auto *a = m_variables->back();
        m_variables->pop_back();
        delete a;
    }

    if (m_variables != NULL) {
        delete m_variables;
    }
}


void RuleWithOperator::updateMatchedVars(Transaction *trans, const std::string &key,
    const std::string &value) {
    ms_dbg_a(trans, 9, "Matched vars updated.");
    trans->m_variableMatchedVar.set(value, trans->m_variableOffset);
    trans->m_variableMatchedVarName.set(key, trans->m_variableOffset);

    trans->m_variableMatchedVars.set(key, value, trans->m_variableOffset);
    trans->m_variableMatchedVarsNames.set(key, key, trans->m_variableOffset);
}


bool RuleWithOperator::executeOperatorAt(Transaction *trans, const std::string &key,
    const std::string &value, RuleMessage &ruleMessage) {
#if MSC_EXEC_CLOCK_ENABLED
    clock_t begin = clock();
    clock_t end;
    double elapsed_s = 0;
#endif
    bool ret;

    ms_dbg_a(trans, 9, "Target value: \"" + utils::string::limitTo(80,
        utils::string::toHexIfNeeded(value)) \
        + "\" (Variable: " + key + ")");

    ret = this->m_operator->evaluateInternal(trans, this, value, ruleMessage);

    if (ret == false) {
        return false;
    }

#if MSC_EXEC_CLOCK_ENABLED
    end = clock();
    elapsed_s = static_cast<double>(end - begin) / CLOCKS_PER_SEC;

    ms_dbg_a(trans, 5, "Operator completed in " + \
        std::to_string(elapsed_s) + " seconds");
#endif
    return ret;
}


template<typename MapType, typename Operation>
void getVariablesExceptionsHelper(
    variables::Variables *exclusion, variables::Variables *addition,
    const MapType &map, Operation op) {
    for (const auto &[x, v] : map) {
        if (op(x)) {
            auto b = v.get();
            if (auto vme = dynamic_cast<variables::VariableModificatorExclusion*>(b)) {
                exclusion->push_back(vme->m_base.get());
            } else {
                addition->push_back(b);
            }
        }
    }
}


void RuleWithOperator::getVariablesExceptions(Transaction &t,
    variables::Variables *exclusion, variables::Variables *addition) {
    getVariablesExceptionsHelper(exclusion, addition,
        t.m_rules->m_exceptions.m_variable_update_target_by_tag, 
        [this, &t](const auto &tag) { return containsTag(*tag.get(), &t); });

    getVariablesExceptionsHelper(exclusion, addition,
        t.m_rules->m_exceptions.m_variable_update_target_by_msg,
        [this, &t](const auto &msg) { return containsMsg(*msg.get(), &t); });

    getVariablesExceptionsHelper(exclusion, addition,
        t.m_rules->m_exceptions.m_variable_update_target_by_id,
        [this](const auto &id) { return m_ruleId == id; });
}


inline void RuleWithOperator::getFinalVars(variables::Variables *vars,
    variables::Variables *exclusion, Transaction *trans) {
    variables::Variables addition;
    getVariablesExceptions(*trans, exclusion, &addition); // cppcheck-suppress ctunullpointer

    for (std::size_t i = 0; i < m_variables->size(); i++) {
        Variable *variable = m_variables->at(i);
        if (exclusion->contains(variable)) {
            continue;
        }
        if (std::find_if(trans->m_ruleRemoveTargetById.begin(),
                trans->m_ruleRemoveTargetById.end(),
                [&, variable, this](const auto &m) -> bool {
                    const auto& str1 = m.second;
                    const auto& str2 = *variable->m_fullName.get();
                    return m.first == m_ruleId &&
                           str1.size() == str2.size() &&
                           std::equal(str1.begin(), str1.end(), str2.begin(),
                                      [](char a, char b) {
                                          return std::tolower(static_cast<unsigned char>(a)) ==
                                                 std::tolower(static_cast<unsigned char>(b));
                                      }); // end-of std::equal
                }) != trans->m_ruleRemoveTargetById.end()) {
            continue;
        }
        if (std::find_if(trans->m_ruleRemoveTargetByTag.begin(),
                    trans->m_ruleRemoveTargetByTag.end(),
                    [&, variable, trans, this](
                        const auto &m) -> bool {
                        return containsTag(m.first, trans)
                            && m.second == *variable->m_fullName.get();
                    }) != trans->m_ruleRemoveTargetByTag.end()) {
            continue;
        }
        vars->push_back(variable);
    }

    for (auto *variable : addition) {
        vars->push_back(variable);
    }
}


bool RuleWithOperator::evaluate(Transaction *trans,
    RuleMessage &ruleMessage) {
    bool globalRet = false;
    bool recursiveGlobalRet;
    bool containsBlock = hasBlockAction();
    std::string eparam;
    variables::Variables vars;
    vars.reserve(4);
    variables::Variables exclusion;

    RuleWithActions::evaluate(trans, ruleMessage);


    // FIXME: Make a class runTimeException to handle this cases.
    for (const auto &i : trans->m_ruleRemoveById) {
        if (m_ruleId != i) {
            continue;
        }
        ms_dbg_a(trans, 9, "Rule id: " + std::to_string(m_ruleId) +
            " was skipped due to a ruleRemoveById action...");
        return true;
    }
    for (const auto &i : trans->m_ruleRemoveByIdRange) {
        if (!(i.first <= m_ruleId && i.second >= m_ruleId)) {
            continue;
        }
        ms_dbg_a(trans, 9, "Rule id: " + std::to_string(m_ruleId) +
            " was skipped due to a ruleRemoveById action...");
        return true;
    }

    if (m_operator->m_string) {
        eparam = m_operator->m_string->evaluate(trans);

        if (m_operator->m_string->containsMacro()) {
            eparam = "\"" + eparam + "\" Was: \"" \
                + m_operator->m_string->evaluate(NULL) + "\"";
        } else {
            eparam = "\"" + eparam + "\"";
        }
    ms_dbg_a(trans, 4, "(Rule: " + std::to_string(m_ruleId) \
        + ") Executing operator \"" + getOperatorName() \
        + "\" with param " \
        + eparam \
        + " against " \
        + m_variables + ".");
    } else {
        ms_dbg_a(trans, 4, "(Rule: " + std::to_string(m_ruleId) \
            + ") Executing operator \"" + getOperatorName() \
            + " against " \
            + m_variables + ".");
    }


    getFinalVars(&vars, &exclusion, trans);

    for (auto &var : vars) {
        std::vector<const VariableValue *> e;
        if (!var) {
            continue;
        }
        var->evaluate(trans, this, &e);
        for (const VariableValue *v : e) {
            const std::string &value = v->getValue();
            const std::string &key = v->getKeyWithCollection();

            if (exclusion.contains(v) ||
                std::find_if(trans->m_ruleRemoveTargetById.begin(),
                    trans->m_ruleRemoveTargetById.end(),
                    [&, v, this](const auto &m) -> bool {
                        return m.first == m_ruleId && m.second == v->getKeyWithCollection();
                    }) != trans->m_ruleRemoveTargetById.end()
            ) {
                delete v;
                v = nullptr;
                continue;
            }
            if (exclusion.contains(v) ||
                std::find_if(trans->m_ruleRemoveTargetByTag.begin(),
                    trans->m_ruleRemoveTargetByTag.end(),
                    [&, v, trans, this](const auto &m) -> bool {
                        return containsTag(m.first, trans) && m.second == v->getKeyWithCollection();
                    }) != trans->m_ruleRemoveTargetByTag.end()
            ) {
                delete v;
                v = nullptr;
                continue;
            }

            TransformationResults values;

            executeTransformations(trans, value, values);

            for (const auto &valueTemp : values) {
                const auto &valueAfterTrans = valueTemp.first;

                const bool ret = executeOperatorAt(trans, key, valueAfterTrans, ruleMessage);

                if (ret == true) {
                    ruleMessage.m_match = m_operator->resolveMatchMessage(trans,
                        key, value);
                    for (const auto &i : v->getOrigin()) {
                        ruleMessage.m_reference.append(i.toText());
                    }

                    ruleMessage.m_reference.append(*valueTemp.second);
                    updateMatchedVars(trans, key, valueAfterTrans);
                    executeActionsIndependentOfChainedRuleResult(trans,
                        &containsBlock, ruleMessage);

                    performLogging(trans, ruleMessage, false);

                    globalRet = true;
                }
            }
            delete v;
            v = NULL;
        }
        e.clear();
        e.reserve(4);
    }

    if (globalRet == false) {
        ms_dbg_a(trans, 4, "Rule returned 0.");
        goto end_clean;
    }
    ms_dbg_a(trans, 4, "Rule returned 1.");

    if (this->isChained() == false) {
        goto end_exec;
    }

    /* FIXME: this check should happens on the parser. */
    if (this->m_chainedRuleChild == nullptr) {
        ms_dbg_a(trans, 4, "Rule is marked as chained but there " \
            "isn't a subsequent rule.");
        goto end_clean;
    }

    ms_dbg_a(trans, 4, "Executing chained rule.");
    recursiveGlobalRet = m_chainedRuleChild->evaluate(trans, ruleMessage);

    if (recursiveGlobalRet == true) {
        goto end_exec;
    }

end_clean:
    return false;

end_exec:
    executeActionsAfterFullMatch(trans, containsBlock, ruleMessage);

    /* last rule in the chain. */
    performLogging(trans, ruleMessage, true, true);
    return true;
}


const std::string& RuleWithOperator::getOperatorName() const { return m_operator->m_op; }


}  // namespace modsecurity
