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

#ifndef SRC_OPERATORS_VERIFY_CPF_H_
#define SRC_OPERATORS_VERIFY_CPF_H_

#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"
#include "src/utils/regex.h"


namespace modsecurity {
using Utils::SMatch;
using Utils::regex_search;
using Utils::Regex;

namespace operators {

class VerifyCPF : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit VerifyCPF(std::unique_ptr<RunTimeString> param)
        : Operator("VerifyCPF", std::move(param)) {
        m_re = new Regex(m_param);
    }

    ~VerifyCPF() {
        delete m_re;
    }

    bool operator=(const VerifyCPF &a) = delete;
    VerifyCPF(const VerifyCPF &a) = delete;

    bool evaluate(Transaction *transaction, RuleWithActions *rule,
        const std::string& input,
        std::shared_ptr<RuleMessage> ruleMessage) override;

    bool verify(const char *ssnumber, int len);

 private:
    static int convert_to_int(const char c);
    Regex *m_re;
    const char bad_cpf[12][12] = { "00000000000",
        "01234567890",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999"};
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VERIFY_CPF_H_
