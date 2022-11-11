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

#include <iostream>
#include <list>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#ifndef SRC_VARIABLES_SESSION_H_
#define SRC_VARIABLES_SESSION_H_

#include "src/variables/variable.h"
#include "src/run_time_string.h"

namespace modsecurity {

class Transaction;
namespace variables {


class Session_DictElement : public Variable {
 public:
    explicit Session_DictElement(std::string dictElement)
        : Variable("SESSION:" + dictElement),
        m_dictElement("SESSION:" + dictElement) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_session_collection->resolveMultiMatches(
            m_name, t->m_collections.m_session_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Session_NoDictElement : public Variable {
 public:
    Session_NoDictElement()
        : Variable("SESSION") { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_session_collection->resolveMultiMatches("",
            t->m_collections.m_session_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }
};


class Session_DictElementRegexp : public VariableRegex {
 public:
    explicit Session_DictElementRegexp(std::string dictElement)
        : VariableRegex("SESSION", dictElement),
        m_dictElement(dictElement) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_session_collection->resolveRegularExpression(
            m_dictElement, t->m_collections.m_session_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Session_DynamicElement : public Variable {
 public:
    explicit Session_DynamicElement(std::unique_ptr<RunTimeString> dictElement)
        : Variable("SESSION:dynamic"),
        m_string(std::move(dictElement)) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        std::string string = m_string->evaluate(t);
        t->m_collections.m_session_collection->resolveMultiMatches(
            string,
            t->m_collections.m_session_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    void del(Transaction *t, std::string k) {
        t->m_collections.m_session_collection->del(k,
            t->m_collections.m_session_collection_key,
            t->m_collections.m_ip_collection_key);
    }

    void storeOrUpdateFirst(Transaction *t, std::string var,
        std::string value) {
        t->m_collections.m_session_collection->storeOrUpdateFirst(
            var, t->m_collections.m_session_collection_key,
            t->m_rules->m_secWebAppId.m_value,
            value);
    }

    std::unique_ptr<RunTimeString> m_string;
};


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_SESSION_H_
