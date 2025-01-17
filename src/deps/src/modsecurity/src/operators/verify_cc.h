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

#ifndef SRC_OPERATORS_VERIFY_CC_H_
#define SRC_OPERATORS_VERIFY_CC_H_

#if WITH_PCRE2
#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>
#else
#include <pcre.h>
#endif


#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"

namespace modsecurity {
namespace operators {

class VerifyCC : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit VerifyCC(std::unique_ptr<RunTimeString> param)
        : Operator("VerifyCC", std::move(param)),
#if WITH_PCRE2
        m_pc(NULL),
        m_pcje(PCRE2_ERROR_JIT_BADOPTION) { }
#else
        m_pc(NULL),
        m_pce(NULL) { }
#endif
    ~VerifyCC();

    bool evaluate(Transaction *t, RuleWithActions *rule,
        const std::string& input,
        std::shared_ptr<RuleMessage> ruleMessage)  override;
    bool init(const std::string &param, std::string *error) override;
 private:
#if WITH_PCRE2
    pcre2_code *m_pc;
    int m_pcje;
#else
    pcre *m_pc;
    pcre_extra *m_pce;
#endif
    static int luhnVerify(const char *ccnumber, int len);
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VERIFY_CC_H_
