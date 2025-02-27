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

#ifndef SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_
#define SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_

#include <string>
#include <memory>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class ValidateUtf8Encoding : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    ValidateUtf8Encoding()
        : Operator("ValidateUtf8Encoding") { }

    bool evaluate(Transaction *transaction, RuleWithActions *rule,
        const std::string &str,
        RuleMessage &ruleMessage) override;

    static int detect_utf8_character(const unsigned char *p_read,
        unsigned int length);
};

}  // namespace operators
}  // namespace modsecurity



#endif  // SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_
