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

#ifdef __cplusplus
#include <stack>
#include <vector>
#include <string>
#include <list>
#include <memory>
#include <utility>
#endif

#ifndef HEADERS_MODSECURITY_RULE_MARKER_H_
#define HEADERS_MODSECURITY_RULE_MARKER_H_

#include "modsecurity/transaction.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/variable_value.h"
#include "modsecurity/rule.h"

#ifdef __cplusplus

namespace modsecurity {


class RuleMarker : public Rule {
 public:
    RuleMarker(
        const std::string &name,
        std::unique_ptr<std::string> fileName,
        int lineNumber)
        : Rule(std::move(fileName), lineNumber),
        m_name(std::make_shared<std::string>(name)) { }

    RuleMarker(const RuleMarker& r) :
        Rule(r),
        m_name(r.m_name)
    { }

    RuleMarker &operator =(const RuleMarker& r) {
        Rule::operator = (r);
        m_name = r.m_name;
        return *this;
    }

    virtual bool evaluate(Transaction *transaction,
        std::shared_ptr<RuleMessage> rm) override {
        return evaluate(transaction);
    }

    virtual bool evaluate(Transaction *transaction) override {
        if (transaction->isInsideAMarker()) {
            if (*transaction->getCurrentMarker() == *m_name) {
                transaction->removeMarker();
                // FIXME: Move this to .cc
                //        ms_dbg_a(transaction, 4, "Out of a SecMarker " + *m_name);
            }
        }

        return true;
    };


    std::shared_ptr<std::string> getName() {
        return m_name;
    }

    bool isMarker() override { return true; }

 private:
    std::shared_ptr<std::string> m_name;
};


}  // namespace modsecurity

#endif

#endif  // HEADERS_MODSECURITY_RULE_MARKER_H_
