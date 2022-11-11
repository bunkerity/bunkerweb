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

#include "src/variables/env.h"

#include <stdlib.h>
#include <stdio.h>

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>
#include <map>

#include "modsecurity/transaction.h"

extern char **environ;

namespace modsecurity {
namespace variables {

void Env::evaluate(Transaction *transaction,
    Rule *rule,
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

    for (auto& x : transaction->m_variableEnvs) {
        if (x.first != m_name && m_name.length() > 0) {
            continue;
        }
        if (!m_keyExclusion.toOmit(x.first)) {
            l->push_back(new VariableValue(&m_collectionName, &x.first,
                &x.second));
        }
    }
}


}  // namespace variables
}  // namespace modsecurity
