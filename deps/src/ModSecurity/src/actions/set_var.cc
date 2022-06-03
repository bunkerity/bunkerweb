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

#include "src/actions/set_var.h"

#include <iostream>
#include <string>
#include <memory>

#include "modsecurity/transaction.h"
#include "modsecurity/rules.h"
#include "modsecurity/rule.h"
#include "src/utils/string.h"
#include "src/variables/global.h"
#include "src/variables/ip.h"
#include "src/variables/resource.h"
#include "src/variables/session.h"
#include "src/variables/tx.h"
#include "src/variables/user.h"
#include "src/variables/variable.h"

namespace modsecurity {
namespace actions {


bool SetVar::init(std::string *error) {
    return true;
}


bool SetVar::evaluate(Rule *rule, Transaction *t) {
    std::string targetValue;
    std::string resolvedPre;

    if (m_string) {
        resolvedPre = m_string->evaluate(t, rule);
    }

    std::string m_variableNameExpanded;
    std::vector<const VariableValue *> l;

    auto *v = m_variable.get();
    variables::Tx_DynamicElement *tx = dynamic_cast<
        variables::Tx_DynamicElement *> (v);
    variables::Session_DynamicElement *session = dynamic_cast<
        variables::Session_DynamicElement *> (v);
    variables::Ip_DynamicElement *ip = dynamic_cast<
        variables::Ip_DynamicElement *> (v);
    variables::Resource_DynamicElement *resource = dynamic_cast<
        variables::Resource_DynamicElement *> (v);
    variables::Global_DynamicElement *global = dynamic_cast<
        variables::Global_DynamicElement *> (v);
    variables::User_DynamicElement *user = dynamic_cast<
        variables::User_DynamicElement *> (v);
    if (tx) {
        m_variableNameExpanded = tx->m_string->evaluate(t, rule);
    } else if (session) {
        m_variableNameExpanded = session->m_string->evaluate(t, rule);
    } else if (ip) {
        m_variableNameExpanded = ip->m_string->evaluate(t, rule);
    } else if (resource) {
        m_variableNameExpanded = resource->m_string->evaluate(t, rule);
    } else if (global) {
        m_variableNameExpanded = global->m_string->evaluate(t, rule);
    } else if (user) {
        m_variableNameExpanded = user->m_string->evaluate(t, rule);
    } else {
        m_variableNameExpanded = m_variable->m_name;
    }

    if (m_operation == setOperation) {
        targetValue = resolvedPre;
    } else if (m_operation == setToOneOperation) {
        targetValue = std::string("1");
    } else if (m_operation == unsetOperation) {
        if (tx) {
            tx->del(t, m_variableNameExpanded);
        } else if (session) {
            session->del(t, m_variableNameExpanded);
        } else if (ip) {
            ip->del(t, m_variableNameExpanded);
        } else if (resource) {
            resource->del(t, m_variableNameExpanded);
        } else if (global) {
            global->del(t, m_variableNameExpanded);
        } else if (user) {
            user->del(t, m_variableNameExpanded);
        } else {
            // ?
        }
        goto end;
    } else {
        int pre = 0;
        int value = 0;

        try {
            pre = stoi(resolvedPre);
        } catch (...) {
            pre = 0;
        }

        try {
            std::vector<const VariableValue *> l;
            m_variable->evaluate(t, rule, &l);
            if (l.size() == 0) {
                value = 0;
            } else {
                value = stoi(l[0]->getValue());
                for (auto &i : l) {
                    delete i;
                }
            }
        } catch (...) {
            value = 0;
        }

        if (m_operation == sumAndSetOperation) {
            targetValue = std::to_string(value + pre);
        } else if (m_operation == substractAndSetOperation) {
            targetValue = std::to_string(value - pre);
        }
    }

    ms_dbg_a(t, 8, "Saving variable: " + m_variable->m_collectionName \
        + ":" + m_variableNameExpanded + " with value: " + targetValue);

    if (tx) {
        tx->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else if (session) {
        session->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else if (ip) {
        ip->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else if (resource) {
        resource->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else if (global) {
        global->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else if (user) {
        user->storeOrUpdateFirst(t, m_variableNameExpanded, targetValue);
    } else {
        // ?
    }

    /*
    t->m_collections.storeOrUpdateFirst(m_variable->m_collectionName,
        m_variableNameExpanded,
        t->m_rules->m_secWebAppId.m_value, targetValue);
    */
end:
    return true;
}

}  // namespace actions
}  // namespace modsecurity
