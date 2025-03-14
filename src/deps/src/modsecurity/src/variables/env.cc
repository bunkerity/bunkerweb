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

#include "src/variables/env.h"

#include <stdlib.h>
#include <stdio.h>

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>
#include <map>

#ifdef WIN32
#include "src/compat/msvc.h"
#endif

#include "modsecurity/transaction.h"

#ifndef WIN32
extern char **environ;
#endif

namespace modsecurity {
namespace variables {

void Env::evaluate(Transaction *transaction,
    RuleWithActions *rule,
    std::vector<const VariableValue *> *l) {
    for (char **current = environ; *current; current++) {
        std::string env = std::string(*current);
        size_t pos = env.find_first_of("=");
        if (pos == std::string::npos) {
            continue;
        }
        std::string key = std::string(env, 0, pos);
        std::string value = std::string(env, pos+1, env.length() - (pos + 1));
        std::pair<std::string, std::string> a(key, value);
        transaction->m_variableEnvs.insert(a);
    }

    const auto hasName = m_name.length() > 0;
    for (const auto& x : transaction->m_variableEnvs) {
#ifndef WIN32
        if (hasName && x.first != m_name) {
#else
        if (hasName && strcasecmp(x.first.c_str(), m_name.c_str()) != 0) {
#endif
            continue;
        }
        // (Windows) we need to keep the case from the rule in case that from
        // the environment differs.
        const auto &key = hasName ? m_name : x.first;
        if (!m_keyExclusion.toOmit(key)) {
            l->push_back(new VariableValue(&m_collectionName, &key,
                &x.second));
        }
    }
}


}  // namespace variables
}  // namespace modsecurity
