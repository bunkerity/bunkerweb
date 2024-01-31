/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <list>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#ifndef SRC_VARIABLES_GLOBAL_H_
#define SRC_VARIABLES_GLOBAL_H_

#include "src/variables/variable.h"
#include "src/run_time_string.h"

namespace modsecurity {

class Transaction;
namespace variables {


class Global_DictElement : public Variable {
 public:
    explicit Global_DictElement(const std::string &dictElement)
        : Variable("GLOBAL:" + dictElement),
        m_dictElement("GLOBAL:" + dictElement) { }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_global_collection->resolveMultiMatches(
            m_name, t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Global_NoDictElement : public Variable {
 public:
    Global_NoDictElement()
        : Variable("GLOBAL") { }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_global_collection->resolveMultiMatches("",
            t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }
};


class Global_DictElementRegexp : public VariableRegex {
 public:
    explicit Global_DictElementRegexp(const std::string &dictElement)
        : VariableRegex("GLOBAL", dictElement),
        m_dictElement(dictElement) { }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_global_collection->resolveRegularExpression(
            m_dictElement,
            t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Global_DynamicElement : public Variable {
 public:
    explicit Global_DynamicElement(std::unique_ptr<RunTimeString> dictElement)
        : Variable("GLOBAL:dynamic"),
        m_string(std::move(dictElement)) { }

    void evaluate(Transaction *t,
        RuleWithActions *rule,
        std::vector<const VariableValue *> *l) override {
        std::string string = m_string->evaluate(t);
        t->m_collections.m_global_collection->resolveMultiMatches(
            string,
            t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    static void del(Transaction *t, const std::string &k) {
        t->m_collections.m_global_collection->del(k,
            t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value);
    }

    static void setExpiry(Transaction *t, const std::string &k, int32_t expiry_seconds) {
        t->m_collections.m_global_collection->setExpiry(k,
            t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value, expiry_seconds);
    }

    static void storeOrUpdateFirst(Transaction *t, const std::string &var,
        const std::string &value) {
        t->m_collections.m_global_collection->storeOrUpdateFirst(
            var, t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value,
            value);
    }

    std::unique_ptr<RunTimeString> m_string;
};


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_GLOBAL_H_
