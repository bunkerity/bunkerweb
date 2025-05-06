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

#ifndef HEADERS_MODSECURITY_RULE_MARKER_H_
#define HEADERS_MODSECURITY_RULE_MARKER_H_

#include "modsecurity/transaction.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/variable_value.h"
#include "modsecurity/rule.h"

#ifdef __cplusplus

#include <string>
#include <memory>

namespace modsecurity {


class RuleMarker : public Rule {
 public:
    RuleMarker(
        const std::string &name,
        const std::string &fileName,
        int lineNumber)
        : Rule(fileName, lineNumber),
        m_name(name) { }

    RuleMarker(const RuleMarker &r) = delete;

    RuleMarker &operator=(const RuleMarker &r) = delete;
   
    virtual bool evaluate(Transaction *transaction, RuleMessage &ruleMessage) override {
        return evaluate(transaction);
    }

    virtual bool evaluate(Transaction *transaction) override {
        if (transaction->isInsideAMarker() &&
            *transaction->getCurrentMarker() == m_name) {
                transaction->removeMarker();
                // FIXME: Move this to .cc
                //        ms_dbg_a(transaction, 4, "Out of a SecMarker " + *m_name);
        }

        return true;
    };

    bool isMarker() override { return true; }

 private:
    const std::string m_name;
};


}  // namespace modsecurity

#endif

#endif  // HEADERS_MODSECURITY_RULE_MARKER_H_
