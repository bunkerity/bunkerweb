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
#include <unordered_map>
#include <list>
#include <vector>
#include <algorithm>
#include <memory>
#endif


#include "modsecurity/variable_value.h"


#ifndef HEADERS_MODSECURITY_COLLECTION_COLLECTION_H_
#define HEADERS_MODSECURITY_COLLECTION_COLLECTION_H_

#ifndef __cplusplus
typedef struct Variable_t Variables;
#endif

#ifdef __cplusplus
namespace modsecurity {
namespace variables {
class KeyExclusions;
}
namespace collection {

class Collection {
 public:
    explicit Collection(std::string a) : m_name(a) { }
    virtual ~Collection() { }
    virtual void store(std::string key, std::string value) = 0;

    virtual bool storeOrUpdateFirst(const std::string &key,
        const std::string &value) = 0;

    virtual bool updateFirst(const std::string &key,
        const std::string &value) = 0;

    virtual void del(const std::string& key) = 0;

    virtual std::unique_ptr<std::string> resolveFirst(
        const std::string& var) = 0;

    virtual void resolveSingleMatch(const std::string& var,
        std::vector<const VariableValue *> *l) = 0;
    virtual void resolveMultiMatches(const std::string& var,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) = 0;
    virtual void resolveRegularExpression(const std::string& var,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) = 0;


    /* store */
    virtual void store(std::string key, std::string compartment,
        std::string value) {
        std::string nkey = compartment + "::" + key;
        store(nkey, value);
    }


    virtual void store(std::string key, std::string compartment,
        std::string compartment2, std::string value) {
        std::string nkey = compartment + "::" + compartment2 + "::" + key;
        store(nkey, value);
    }


    /* storeOrUpdateFirst */
    virtual bool storeOrUpdateFirst(const std::string &key,
        std::string compartment, const std::string &value) {
        std::string nkey = compartment + "::" + key;
        return storeOrUpdateFirst(nkey, value);
    }


    virtual bool storeOrUpdateFirst(const std::string &key,
        std::string compartment, std::string compartment2,
        const std::string &value) {
        std::string nkey = compartment + "::" + compartment2 + "::" + key;
        return storeOrUpdateFirst(nkey, value);
    }


    /* updateFirst */
    virtual bool updateFirst(const std::string &key, std::string compartment,
        const std::string &value) {
        std::string nkey = compartment + "::" + key;
        return updateFirst(nkey, value);
    }


    virtual bool updateFirst(const std::string &key, std::string compartment,
        std::string compartment2, const std::string &value) {
        std::string nkey = compartment + "::" + compartment2 + "::" + key;
        return updateFirst(nkey, value);
    }


    /* del */
    virtual void del(const std::string& key, std::string compartment) {
        std::string nkey = compartment + "::" + key;
        del(nkey);
    }


    virtual void del(const std::string& key, std::string compartment,
        std::string compartment2) {
        std::string nkey = compartment + "::" + compartment2 + "::" + key;
        del(nkey);
    }


    /* resolveFirst */
    virtual std::unique_ptr<std::string> resolveFirst(const std::string& var,
        std::string compartment) {
        std::string nkey = compartment + "::" + var;
        return resolveFirst(nkey);
    }


    virtual std::unique_ptr<std::string> resolveFirst(const std::string& var,
        std::string compartment, std::string compartment2) {
        std::string nkey = compartment + "::" + compartment2 + "::" + var;
        return resolveFirst(nkey);
    }


    /* resolveSingleMatch */
    virtual void resolveSingleMatch(const std::string& var,
        std::string compartment, std::vector<const VariableValue *> *l) {
        std::string nkey = compartment + "::" + var;
        resolveSingleMatch(nkey, l);
    }


    virtual void resolveSingleMatch(const std::string& var,
        std::string compartment, std::string compartment2,
        std::vector<const VariableValue *> *l) {
        std::string nkey = compartment + "::" + compartment2 + "::" + var;
        resolveSingleMatch(nkey, l);
    }


    /* resolveMultiMatches */
    virtual void resolveMultiMatches(const std::string& var,
        std::string compartment, std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) {
        std::string nkey = compartment + "::" + var;
        resolveMultiMatches(nkey, l, ke);
    }


    virtual void resolveMultiMatches(const std::string& var,
        std::string compartment, std::string compartment2,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) {
        std::string nkey = compartment + "::" + compartment2 + "::" + var;
        resolveMultiMatches(nkey, l, ke);
    }


    /* resolveRegularExpression */
    virtual void resolveRegularExpression(const std::string& var,
        std::string compartment, std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) {
        std::string nkey = compartment + "::" + var;
        resolveRegularExpression(nkey, l, ke);
    }


    virtual void resolveRegularExpression(const std::string& var,
        std::string compartment, std::string compartment2,
        std::vector<const VariableValue *> *l, variables::KeyExclusions &ke) {
        std::string nkey = compartment + "::" + compartment2 + "::" + var;
        resolveRegularExpression(nkey, l, ke);
    }

    std::string m_name;
};

}  // namespace collection
}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_COLLECTION_COLLECTION_H_
