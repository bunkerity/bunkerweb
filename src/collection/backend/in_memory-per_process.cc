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


#include "src/collection/backend/in_memory-per_process.h"

#ifdef __cplusplus
#include <string>
#include <iostream>
#include <unordered_map>
#include <list>
#include <memory>
#endif

#include <pthread.h>

#include "modsecurity/variable_value.h"
#include "src/utils/regex.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace collection {
namespace backend {


InMemoryPerProcess::InMemoryPerProcess(const std::string &name) :
    Collection(name) {
    this->reserve(1000);
    pthread_mutex_init(&m_lock, NULL);
}

InMemoryPerProcess::~InMemoryPerProcess() {
    this->clear();
    pthread_mutex_destroy(&m_lock);
}

void InMemoryPerProcess::store(std::string key, std::string value) {
    pthread_mutex_lock(&m_lock);
    this->emplace(key, value);
    pthread_mutex_unlock(&m_lock);
}


bool InMemoryPerProcess::storeOrUpdateFirst(const std::string &key,
    const std::string &value) {
    if (updateFirst(key, value) == false) {
        store(key, value);
    }
    return true;
}


bool InMemoryPerProcess::updateFirst(const std::string &key,
    const std::string &value) {
    pthread_mutex_lock(&m_lock);
    auto range = this->equal_range(key);

    for (auto it = range.first; it != range.second; ++it) {
        it->second = value;
        pthread_mutex_unlock(&m_lock);
        return true;
    }
    pthread_mutex_unlock(&m_lock);
    return false;
}


void InMemoryPerProcess::del(const std::string& key) {
    pthread_mutex_lock(&m_lock);
    this->erase(key);
    pthread_mutex_unlock(&m_lock);
}


void InMemoryPerProcess::resolveSingleMatch(const std::string& var,
    std::vector<const VariableValue *> *l) {
    auto range = this->equal_range(var);

    for (auto it = range.first; it != range.second; ++it) {
        l->push_back(new VariableValue(&m_name, &it->first, &it->second));
    }
}


void InMemoryPerProcess::resolveMultiMatches(const std::string& var,
    std::vector<const VariableValue *> *l, variables::KeyExclusions &ke) {
    size_t keySize = var.size();
    l->reserve(15);

    if (keySize == 0) {
        for (auto &i : *this) {
            if (ke.toOmit(i.first)) {
                continue;
            }
            l->insert(l->begin(), new VariableValue(&m_name, &i.first,
                &i.second));
        }
    } else {
        auto range = this->equal_range(var);
        for (auto it = range.first; it != range.second; ++it) {
            if (ke.toOmit(var)) {
                continue;
            }
            l->insert(l->begin(), new VariableValue(&m_name, &var,
                &it->second));
        }
    }
}


void InMemoryPerProcess::resolveRegularExpression(const std::string& var,
    std::vector<const VariableValue *> *l, variables::KeyExclusions &ke) {

    //if (var.find(":") == std::string::npos) {
    //    return;
    //}
    //if (var.size() < var.find(":") + 3) {
    //    return;
    //}
    //std::string col = std::string(var, 0, var.find(":"));
    //std::string name = std::string(var, var.find(":") + 2,
    //    var.size() - var.find(":") - 3);
    //size_t keySize = col.size();
    Utils::Regex r(var, true);

    for (const auto& x : *this) {
        //if (x.first.size() <= keySize + 1) {
        //    continue;
        //}
        //if (x.first.at(keySize) != ':') {
        //    continue;
        //}
        //if (std::string(x.first, 0, keySize) != col) {
        //    continue;
        //}
        //std::string content = std::string(x.first, keySize + 1,
         //                                 x.first.size() - keySize - 1);
        int ret = Utils::regex_search(x.first, r);
        if (ret <= 0) {
            continue;
        }
        if (ke.toOmit(x.first)) {
            continue;
        }
        l->insert(l->begin(), new VariableValue(&m_name, &x.first, &x.second));
    }
}


std::unique_ptr<std::string> InMemoryPerProcess::resolveFirst(
    const std::string& var) {
    auto range = equal_range(var);
    for (auto it = range.first; it != range.second; ++it) {
        return std::unique_ptr<std::string>(new std::string(it->second));
    }

    return NULL;
}


}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
