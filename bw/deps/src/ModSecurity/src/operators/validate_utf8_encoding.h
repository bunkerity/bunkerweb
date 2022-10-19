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

#ifndef SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_
#define SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_

#include <string>
#include <memory>

#include "src/operators/operator.h"


#define UNICODE_ERROR_CHARACTERS_MISSING    -1
#define UNICODE_ERROR_INVALID_ENCODING      -2
#define UNICODE_ERROR_OVERLONG_CHARACTER    -3
#define UNICODE_ERROR_RESTRICTED_CHARACTER  -4
#define UNICODE_ERROR_DECODING_ERROR        -5


namespace modsecurity {
namespace operators {

class ValidateUtf8Encoding : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    ValidateUtf8Encoding()
        : Operator("ValidateUtf8Encoding") { }

    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &str,
        std::shared_ptr<RuleMessage> ruleMessage) override;

    int detect_utf8_character(const unsigned char *p_read,
        unsigned int length);
};

}  // namespace operators
}  // namespace modsecurity



#endif  // SRC_OPERATORS_VALIDATE_UTF8_ENCODING_H_
