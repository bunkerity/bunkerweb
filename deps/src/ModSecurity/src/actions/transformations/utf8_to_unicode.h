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
#include "src/actions/transformations/transformation.h"

#ifndef SRC_ACTIONS_TRANSFORMATIONS_UTF8_TO_UNICODE_H_
#define SRC_ACTIONS_TRANSFORMATIONS_UTF8_TO_UNICODE_H_

#define UNICODE_ERROR_CHARACTERS_MISSING    -1
#define UNICODE_ERROR_INVALID_ENCODING      -2
#define UNICODE_ERROR_OVERLONG_CHARACTER    -3
#define UNICODE_ERROR_RESTRICTED_CHARACTER  -4
#define UNICODE_ERROR_DECODING_ERROR        -5

namespace modsecurity {
class Transaction;

namespace actions {
namespace transformations {

class Utf8ToUnicode : public Transformation {
 public:
    explicit Utf8ToUnicode(std::string action) : Transformation(action) { }

    std::string evaluate(std::string exp,
        Transaction *transaction) override;

    static char *inplace(unsigned char *input, uint64_t input_len,
        int *changed);
};

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity


#endif  // SRC_ACTIONS_TRANSFORMATIONS_UTF8_TO_UNICODE_H_
