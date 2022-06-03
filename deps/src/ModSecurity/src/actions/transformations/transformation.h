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

#include "modsecurity/actions/action.h"

#ifndef SRC_ACTIONS_TRANSFORMATIONS_TRANSFORMATION_H_
#define SRC_ACTIONS_TRANSFORMATIONS_TRANSFORMATION_H_


namespace modsecurity {
class Transaction;

namespace actions {
namespace transformations {

class Transformation : public Action {
 public:
    explicit Transformation(const std::string& _action)
        : Action(_action, RunTimeBeforeMatchAttemptKind) { }

    explicit Transformation(const std::string& _action, int kind)
        : Action(_action, kind) { }

    std::string evaluate(std::string exp,
        Transaction *transaction) override;

    static Transformation* instantiate(std::string a);
};

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity


#endif  // SRC_ACTIONS_TRANSFORMATIONS_TRANSFORMATION_H_
