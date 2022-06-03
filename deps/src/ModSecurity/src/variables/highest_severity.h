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

#include <vector>
#include <string>
#include <list>
#include <utility>

#ifndef SRC_VARIABLES_HIGHEST_SEVERITY_H_
#define SRC_VARIABLES_HIGHEST_SEVERITY_H_

#include "src/variables/variable.h"

namespace modsecurity {

class Transaction;
namespace variables {

class HighestSeverity : public Variable {
 public:
    explicit HighestSeverity(std::string _name)
        : Variable(_name)
    { }

    void evaluate(Transaction *transaction,
        Rule *rule,
        std::vector<const VariableValue *> *l) override;
};


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_HIGHEST_SEVERITY_H_
