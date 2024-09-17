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

#ifndef SRC_ACTIONS_TRANSFORMATIONS_PARITY_ODD_7BIT_H_
#define SRC_ACTIONS_TRANSFORMATIONS_PARITY_ODD_7BIT_H_

#include "transformation.h"

namespace modsecurity::actions::transformations {

class ParityOdd7bit : public Transformation {
 public:
    using Transformation::Transformation;

    bool transform(std::string &value, const Transaction *trans) const override;
};

}  // namespace modsecurity::actions::transformations

#endif  // SRC_ACTIONS_TRANSFORMATIONS_PARITY_ODD_7BIT_H_
