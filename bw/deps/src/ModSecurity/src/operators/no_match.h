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

#include <string>

#include "modsecurity/transaction.h"
#include "src/operators/operator.h"


#ifndef SRC_OPERATORS_NO_MATCH_H_
#define SRC_OPERATORS_NO_MATCH_H_


namespace modsecurity {
namespace operators {

class NoMatch : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    NoMatch()
        : Operator("NoMatch") { }

    bool evaluate(Transaction *transaction, const std::string &str) override;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_NO_MATCH_H_
