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

#ifndef SRC_VARIABLES_IP_H_
#define SRC_VARIABLES_IP_H_

#include "src/variables/variable.h"
#include "src/run_time_string.h"

namespace modsecurity {

class Transaction;
namespace variables {


class Ip_DictElement : public Variable {
 public:
    explicit Ip_DictElement(std::string dictElement)
        : Variable("IP:" + dictElement),
        m_dictElement("IP:" + dictElement) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_ip_collection->resolveMultiMatches(
            m_name, t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Ip_NoDictElement : public Variable {
 public:
    Ip_NoDictElement()
        : Variable("IP") { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_ip_collection->resolveMultiMatches("",
            t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }
};


class Ip_DictElementRegexp : public VariableRegex {
 public:
    explicit Ip_DictElementRegexp(std::string dictElement)
        : VariableRegex("IP", dictElement),
        m_dictElement(dictElement) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        t->m_collections.m_ip_collection->resolveRegularExpression(
            m_dictElement, t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    std::string m_dictElement;
};


class Ip_DynamicElement : public Variable {
 public:
    explicit Ip_DynamicElement(std::unique_ptr<RunTimeString> dictElement)
        : Variable("IP:dynamic"),
        m_string(std::move(dictElement)) { }

    void evaluate(Transaction *t,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        std::string string = m_string->evaluate(t);
        t->m_collections.m_ip_collection->resolveMultiMatches(
            string,
            t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value, l, m_keyExclusion);
    }

    void del(Transaction *t, std::string k) {
        t->m_collections.m_ip_collection->del(k,
            t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value);
    }

    void storeOrUpdateFirst(Transaction *t, std::string var,
        std::string value) {
        t->m_collections.m_ip_collection->storeOrUpdateFirst(
            var, t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value,
            value);
    }

    std::unique_ptr<RunTimeString> m_string;
};


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_IP_H_
