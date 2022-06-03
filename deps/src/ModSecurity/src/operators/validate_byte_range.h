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

#ifndef SRC_OPERATORS_VALIDATE_BYTE_RANGE_H_
#define SRC_OPERATORS_VALIDATE_BYTE_RANGE_H_

#include <string>
#include <vector>
#include <cstring>
#include <memory>
#include <utility>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class ValidateByteRange : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit ValidateByteRange(std::unique_ptr<RunTimeString> param)
        : Operator("ValidateByteRange", std::move(param)) {
            std::memset(table, '\0', sizeof(char) * 32);
        }
    ~ValidateByteRange() override { }

    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &input,
        std::shared_ptr<RuleMessage> ruleMessage) override;
    bool getRange(const std::string &rangeRepresentation, std::string *error);
    bool init(const std::string& file, std::string *error) override;
 private:
    std::vector<std::string> ranges;
    char table[32];
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VALIDATE_BYTE_RANGE_H_
