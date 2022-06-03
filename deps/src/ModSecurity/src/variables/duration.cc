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

#include "src/variables/duration.h"

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>

#include "modsecurity/transaction.h"
#include "src/utils/system.h"

namespace modsecurity {
namespace variables {

void Duration::evaluate(Transaction *transaction,
    Rule *rule,
    std::vector<const VariableValue *> *l) {
    double e = utils::cpu_seconds() - transaction->m_creationTimeStamp;

    transaction->m_variableDuration.assign(std::to_string(e));

    l->push_back(new VariableValue(&m_retName,
        &transaction->m_variableDuration));
}


}  // namespace variables
}  // namespace modsecurity
