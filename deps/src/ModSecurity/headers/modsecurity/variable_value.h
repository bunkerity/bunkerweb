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


#ifdef __cplusplus
#include <string>
#include <iostream>
#include <memory>
#include <list>
#include <utility>
#endif

#include "modsecurity/variable_origin.h"

#ifndef HEADERS_MODSECURITY_VARIABLE_VALUE_H_
#define HEADERS_MODSECURITY_VARIABLE_VALUE_H_

#ifndef __cplusplus
typedef struct Variable_t VariableValue;
#endif

#ifdef __cplusplus
namespace modsecurity {

class Collection;
class VariableValue {
 public:
    using Origins = std::list<std::unique_ptr<VariableOrigin>>;

    VariableValue(const std::string *key,
        const std::string *value = nullptr)
        : m_key(*key),
        m_keyWithCollection(*key),
        m_collection(""),
        m_value(value != nullptr?*value:"")
    { }

    VariableValue(const std::string *collection,
        const std::string *key,
        const std::string *value)
        : m_key(*key),
        m_keyWithCollection(*collection + ":" + *key),
        m_collection(*collection),
        m_value(*value)
    { }

    explicit VariableValue(const VariableValue *o) :
        m_key(o->m_key),
        m_value(o->m_value),
        m_collection(o->m_collection),
        m_keyWithCollection(o->m_keyWithCollection)
    {
        for (auto &i : o->m_orign) {
            std::unique_ptr<VariableOrigin> origin(new VariableOrigin());
            origin->m_offset = i->m_offset;
            origin->m_length = i->m_length;
            m_orign.push_back(std::move(origin));
        }
    }


    const std::string& getKey() const {
        return m_key;
    }


    const std::string& getKeyWithCollection() const {
        return m_keyWithCollection;
    }


    const std::string& getCollection() const {
        return m_collection;
    }


    const std::string& getValue() const {
        return m_value;
    }


    void setValue(const std::string &value) {
        m_value = value;
    }


    void addOrigin(std::unique_ptr<VariableOrigin> origin) {
        m_orign.push_back(std::move(origin));
    }


    const Origins& getOrigin() const {
        return m_orign;
    }

 private:
    Origins m_orign;
    std::string m_collection;
    std::string m_key;
    std::string m_keyWithCollection;
    std::string m_value;
};

}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_VARIABLE_VALUE_H_
