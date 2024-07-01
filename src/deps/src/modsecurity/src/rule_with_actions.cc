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

#include "modsecurity/rule.h"

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
#include "modsecurity/rule_with_actions.h"
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
using actions::transformations::Transformation;



RuleWithActions::RuleWithActions(
    Actions *actions,
    Transformations *transformations,
    std::unique_ptr<std::string> fileName,
    int lineNumber)
    : Rule(std::move(fileName), lineNumber),
    m_rev(""),
    m_ver(""),
    m_accuracy(0),
    m_maturity(0),
    m_ruleId(0),
    m_chainedRuleChild(nullptr),
    m_chainedRuleParent(nullptr),
    m_disruptiveAction(nullptr),
    m_logData(nullptr),
    m_msg(nullptr),
    m_severity(nullptr),
    m_actionsRuntimePos(),
    m_actionsSetVar(),
    m_actionsTag(),
    m_transformations(transformations != NULL ? *transformations : Transformations()),
    m_containsCaptureAction(false),
    m_containsMultiMatchAction(false),
    m_containsStaticBlockAction(false),
    m_isChained(false) {

    if (transformations != NULL) {
        delete transformations;
    }

    if (actions) {
        for (Action *a : *actions) {
            if (a->action_kind == Action::ConfigurationKind) {
                a->evaluate(this, NULL);
                delete a;

            } else if (a->action_kind == Action::RunTimeOnlyIfMatchKind) {
                if (dynamic_cast<actions::Capture *>(a)) {
                    m_containsCaptureAction = true;
                    delete a;
                } else if (dynamic_cast<actions::MultiMatch *>(a)) {
                    m_containsMultiMatchAction = true;
                    delete a;
                } else if (dynamic_cast<actions::Severity *>(a)) {
                    m_severity = dynamic_cast<actions::Severity *>(a);
                } else if (dynamic_cast<actions::LogData *>(a)) {
                    m_logData = dynamic_cast<actions::LogData*>(a);
                } else if (dynamic_cast<actions::Msg *>(a)) {
                    m_msg = dynamic_cast<actions::Msg*>(a);
                } else if (dynamic_cast<actions::SetVar *>(a)) {
                    m_actionsSetVar.push_back(
                        dynamic_cast<actions::SetVar *>(a));
                } else if (dynamic_cast<actions::Tag *>(a)) {
                    m_actionsTag.push_back(dynamic_cast<actions::Tag *>(a));
                } else if (dynamic_cast<actions::Block *>(a)) {
                    m_actionsRuntimePos.push_back(a);
                    m_containsStaticBlockAction = true;
                } else if (a->isDisruptive() == true) {
                    if (m_disruptiveAction != nullptr) {
                        delete m_disruptiveAction;
                        m_disruptiveAction = nullptr;
                    }
                    m_disruptiveAction = a;
                } else {
                    m_actionsRuntimePos.push_back(a);
                }
            } else {
                delete a;
                std::cout << "General failure, action: " << a->m_name;
                std::cout << " has an unknown type." << std::endl;
                throw;
            }
        }
        delete actions;
    }
}

RuleWithActions::~RuleWithActions() {
    if (m_severity) {
        delete m_severity;
        m_severity = nullptr;
    }
    if (m_logData) {
        delete m_logData;
        m_logData = nullptr;
    }
    if (m_msg) {
        delete m_msg;
        m_msg = nullptr;
    }
    while (m_transformations.empty() == false) {
        auto *a = m_transformations.back();
        m_transformations.pop_back();
        delete a;
    }
    while (m_actionsRuntimePos.empty() == false) {
        auto *a = m_actionsRuntimePos.back();
        m_actionsRuntimePos.pop_back();
        delete a;
    }
    while (m_actionsSetVar.empty() == false) {
        auto *a = m_actionsSetVar.back();
        m_actionsSetVar.pop_back();
        delete a;
    }
    while (m_actionsTag.empty() == false) {
        auto *a = m_actionsTag.back();
        m_actionsTag.pop_back();
        delete a;
    }
    if (m_disruptiveAction != nullptr) {
        delete m_disruptiveAction;
        m_disruptiveAction = nullptr;
    }
}


bool RuleWithActions::evaluate(Transaction *transaction) {
    RuleMessage rm(this, transaction);
    std::shared_ptr<RuleMessage> rm2 = std::make_shared<RuleMessage>(&rm);
    return evaluate(transaction, rm2);
}


bool RuleWithActions::evaluate(Transaction *transaction,
    std::shared_ptr<RuleMessage> ruleMessage) {

    /* Rule evaluate is pure virtual.
     *
     * Rule::evaluate(transaction, ruleMessage);
     */

    /* Matched vars needs to be clear at every new rule execution */
    transaction->m_matched.clear();

    return true;
}


void RuleWithActions::executeActionsIndependentOfChainedRuleResult(Transaction *trans,
    bool *containsBlock, std::shared_ptr<RuleMessage> ruleMessage) {

    for (actions::SetVar *a : m_actionsSetVar) {
        ms_dbg_a(trans, 4, "Running [independent] (non-disruptive) " \
            "action: " + *a->m_name.get());

        a->evaluate(this, trans);
    }

    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pre_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        actions::Action *a = dynamic_cast<actions::Action*>(b.second.get());
        if (a->isDisruptive() == true && *a->m_name.get() == "block") {
            ms_dbg_a(trans, 9, "Rule contains a `block' action");
                *containsBlock = true;
        } else if (*a->m_name.get() == "setvar") {
            ms_dbg_a(trans, 4, "Running [independent] (non-disruptive) " \
                "action: " + *a->m_name.get());
            a->evaluate(this, trans, ruleMessage);
        }
    }

    if (m_containsMultiMatchAction && m_chainedRuleParent == nullptr) {
        if (m_severity) {
            m_severity->evaluate(this, trans, ruleMessage);
        }
        if (m_logData) {
            m_logData->evaluate(this, trans, ruleMessage);
        }
        if (m_msg) {
            m_msg->evaluate(this, trans, ruleMessage);
        }
        for (actions::Tag *a : m_actionsTag) {
            a->evaluate(this, trans, ruleMessage);
        }
    }

}


void RuleWithActions::executeActionsAfterFullMatch(Transaction *trans,
    bool containsBlock, std::shared_ptr<RuleMessage> ruleMessage) {
    bool disruptiveAlreadyExecuted = false;

    for (auto &a : trans->m_rules->m_defaultActions[getPhase()]) {
        if (a.get()->action_kind != actions::Action::RunTimeOnlyIfMatchKind) {
            continue;
        }
        if (!a.get()->isDisruptive()) {
            executeAction(trans, containsBlock, ruleMessage, a.get(), true);
        }
    }

    for (actions::Tag *a : this->m_actionsTag) {
        ms_dbg_a(trans, 4, "Running (non-disruptive) action: " \
            + *a->m_name.get());
        a->evaluate(this, trans, ruleMessage);
    }

    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pos_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        actions::Action *a = dynamic_cast<actions::Action*>(b.second.get());
        executeAction(trans, containsBlock, ruleMessage, a, false);
        disruptiveAlreadyExecuted = true;
    }
    if (m_severity) {
        m_severity->evaluate(this, trans, ruleMessage);
    }

    if (m_logData) {
        m_logData->evaluate(this, trans, ruleMessage);
    }

    if (m_msg) {
        m_msg->evaluate(this, trans, ruleMessage);
    }
    for (Action *a : this->m_actionsRuntimePos) {
        if (!a->isDisruptive()
                && !(disruptiveAlreadyExecuted
                && dynamic_cast<actions::Block *>(a))) {
            executeAction(trans, containsBlock, ruleMessage, a, false);
        }
    }
    if (!disruptiveAlreadyExecuted && m_disruptiveAction != nullptr) {
        executeAction(trans, containsBlock, ruleMessage,
            m_disruptiveAction, false);
    }
}


void RuleWithActions::executeAction(Transaction *trans,
    bool containsBlock, std::shared_ptr<RuleMessage> ruleMessage,
    Action *a, bool defaultContext) {
    if (a->isDisruptive() == false && *a->m_name.get() != "block") {
        ms_dbg_a(trans, 9, "Running " \
            "action: " + *a->m_name.get());
        a->evaluate(this, trans, ruleMessage);
        return;
    }

    if (defaultContext && !containsBlock) {
        ms_dbg_a(trans, 4, "Ignoring action: " + *a->m_name.get() + \
            " (rule does not cotains block)");
        return;
    }

    if (trans->getRuleEngineState() == RulesSet::EnabledRuleEngine) {
        ms_dbg_a(trans, 4, "Running (disruptive)     action: " + *a->m_name.get() + \
            ".");
        a->evaluate(this, trans, ruleMessage);
        return;
    }

    ms_dbg_a(trans, 4, "Not running any disruptive action (or block): " \
        + *a->m_name.get() + ". SecRuleEngine is not On.");
}


inline void RuleWithActions::executeTransformation(
    actions::transformations::Transformation *a,
    std::shared_ptr<std::string> *value,
    Transaction *trans,
    TransformationResults *ret,
    std::string *path,
    int *nth) const {

    std::string *oldValue = (*value).get();
    std::string newValue = a->evaluate(*oldValue, trans);

    if (newValue != *oldValue) {
        std::shared_ptr<std::string> u(new std::string(newValue));
        if (m_containsMultiMatchAction) {
            ret->push_back(std::make_pair(u, a->m_name));
            (*nth)++;
        }
        *value = u;
    }

    if (path->empty()) {
        path->append(*a->m_name.get());
    } else {
        path->append("," + *a->m_name.get());
    }

    ms_dbg_a(trans, 9, " T (" + \
        std::to_string(*nth) + ") " + \
        *a->m_name.get() + ": \"" + \
        utils::string::limitTo(80, newValue) +"\"");
}

void RuleWithActions::executeTransformations(
    Transaction *trans, const std::string &in, TransformationResults &ret) {
    int none = 0;
    int transformations = 0;
    std::string path("");
    std::shared_ptr<std::string> value =
        std::shared_ptr<std::string>(new std::string(in));

    if (m_containsMultiMatchAction == true) {
        /* keep the original value */
        ret.push_back(std::make_pair(
            std::shared_ptr<std::string>(new std::string(*value)),
            std::shared_ptr<std::string>(new std::string(path))));
    }

    for (Action *a : m_transformations) {
        if (a->m_isNone) {
            none++;
        }
    }

    // Check for transformations on the SecDefaultAction
    // Notice that first we make sure that won't be a t:none
    // on the target rule.
    if (none == 0) {
        for (auto &a : trans->m_rules->m_defaultActions[getPhase()]) {
            if (a->action_kind \
                != actions::Action::RunTimeBeforeMatchAttemptKind) {
                continue;
            }

            // FIXME: here the object needs to be a transformation already.
            Transformation *t = dynamic_cast<Transformation *>(a.get());
            executeTransformation(t, &value, trans, &ret, &path,
                &transformations);
        }
    }

    for (Transformation *a : m_transformations) {
        if (none == 0) {
            Transformation *t = dynamic_cast<Transformation *>(a);
            executeTransformation(t, &value, trans, &ret, &path,
                &transformations);
        }
        if (a->m_isNone) {
            none--;
        }
    }

    // FIXME: It can't be something different from transformation. Sort this
    //        on rules compile time.
    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pre_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        Transformation *a = dynamic_cast<Transformation*>(b.second.get());
        if (a->m_isNone) {
            none++;
        }
    }

    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pre_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        Transformation *a = dynamic_cast<Transformation*>(b.second.get());
        if (none == 0) {
            Transformation *t = dynamic_cast<Transformation *>(a);
            executeTransformation(t, &value, trans, &ret, &path,
                &transformations);
        }
        if (a->m_isNone) {
            none--;
        }
    }

    if (m_containsMultiMatchAction == true) {
        ms_dbg_a(trans, 9, "multiMatch is enabled. " \
            + std::to_string(ret.size()) + \
            " values to be tested.");
    }

    if (!m_containsMultiMatchAction) {
        ret.push_back(std::make_pair(
            std::shared_ptr<std::string>(new std::string(*value)),
            std::shared_ptr<std::string>(new std::string(path))));
    }
}


bool RuleWithActions::containsTag(const std::string& name, Transaction *t) {
    for (auto &tag : m_actionsTag) {
        if (tag != NULL && tag->getName(t) == name) {
            return true;
        }
    }
    return false;
}


bool RuleWithActions::containsMsg(const std::string& name, Transaction *t) {
    return m_msg && m_msg->data(t) == name;
}


std::vector<actions::Action *> RuleWithActions::getActionsByName(const std::string& name,
    Transaction *trans) {
    std::vector<actions::Action *> ret;
    for (auto &z : m_actionsRuntimePos) {
        if (*z->m_name.get() == name) {
            ret.push_back(z);
        }
    }
    for (auto &z : m_transformations) {
        if (*z->m_name.get() == name) {
            ret.push_back(z);
        }
    }
    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pre_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        actions::Action *z = dynamic_cast<actions::Action*>(b.second.get());
        if (*z->m_name.get() == name) {
            ret.push_back(z);
        }
    }
    for (auto &b :
        trans->m_rules->m_exceptions.m_action_pos_update_target_by_id) {
        if (m_ruleId != b.first) {
            continue;
        }
        actions::Action *z = dynamic_cast<actions::Action*>(b.second.get());
        if (*z->m_name.get() == name) {
            ret.push_back(z);
        }
    }
    return ret;
}

void RuleWithActions::performLogging(Transaction *trans,
    std::shared_ptr<RuleMessage> ruleMessage,
    bool lastLog,
    bool chainedParentNull) {

    /* last rule in the chain. */
    bool isItToBeLogged = ruleMessage->m_saveMessage;

    /**
    *
    * RuleMessage is stacked allocated for the rule execution,
    * anything beyond this may lead to invalid pointer access.
    *
    * In case of a warning, o set of messages is saved to be read
    * at audit log generation. Therefore demands a copy here.
    *
    * FIXME: Study an way to avoid the copy.
    *
    **/
    if (lastLog) {
        if (chainedParentNull) {
            isItToBeLogged = (ruleMessage->m_saveMessage && (m_chainedRuleParent == nullptr));
            if (isItToBeLogged && !hasMultimatch()) {
                /* warn */
                trans->m_rulesMessages.push_back(*ruleMessage);

                /* error */
                if (!ruleMessage->m_isDisruptive) {
                    trans->serverLog(ruleMessage);
                }
            }
        } else if (hasBlockAction() && !hasMultimatch()) {
            /* warn */
            trans->m_rulesMessages.push_back(*ruleMessage);
            /* error */
            if (!ruleMessage->m_isDisruptive) {
                trans->serverLog(ruleMessage);
            }
        } else {
            if (isItToBeLogged && !hasMultimatch()
                && !ruleMessage->m_message.empty()) {
                /* warn */
                trans->m_rulesMessages.push_back(*ruleMessage);

                /* error */
                if (!ruleMessage->m_isDisruptive) {
                    trans->serverLog(ruleMessage);
                }
            }
        }
    } else {
        if (hasMultimatch() && isItToBeLogged) {
            /* warn */
            trans->m_rulesMessages.push_back(*ruleMessage.get());

            /* error */
            if (!ruleMessage->m_isDisruptive) {
                trans->serverLog(ruleMessage);
            }

            RuleMessage *rm = new RuleMessage(this, trans);
            rm->m_saveMessage = ruleMessage->m_saveMessage;
            ruleMessage.reset(rm);
        }
    }
}

std::string RuleWithActions::logData(Transaction *t) { return m_logData->data(t); }
std::string RuleWithActions::msg(Transaction *t) { return m_msg->data(t); }
int RuleWithActions::severity() const { return m_severity->m_severity; }


}  // namespace modsecurity
