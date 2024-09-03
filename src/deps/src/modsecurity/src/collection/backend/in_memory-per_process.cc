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


#include "src/collection/backend/in_memory-per_process.h"
#include "src/collection/backend/collection_data.h"

#ifdef __cplusplus
#include <string>
#include <iostream>
#include <unordered_map>
#include <list>
#include <memory>
#endif

#include "modsecurity/variable_value.h"
#include "src/utils/regex.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace collection {
namespace backend {


InMemoryPerProcess::InMemoryPerProcess(const std::string &name) :
    Collection(name) {
    m_map.reserve(1000);
}

InMemoryPerProcess::~InMemoryPerProcess() {
    m_map.clear();
}


template<typename Map>
inline void __store(Map &map, std::string key, std::string value) {
    // NOTE: should be called with write-lock previously acquired

    map.emplace(key, value);
}


template<typename Map>
inline bool __updateFirst(Map &map,
    const std::string &key,
    const std::string &value) {
    // NOTE: should be called with write-lock previously acquired

    if (auto search = map.find(key); search != map.end()) {
        search->second.setValue(value);
        return true;
    }

    return false;
}


void InMemoryPerProcess::store(const std::string &key, const std::string &value) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)
    __store(m_map, key, value);
}


bool InMemoryPerProcess::storeOrUpdateFirst(const std::string &key,
    const std::string &value) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)
    if (__updateFirst(m_map, key, value) == false) {
        __store(m_map, key, value);
    }
    return true;
}


bool InMemoryPerProcess::updateFirst(const std::string &key,
    const std::string &value) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)
    return __updateFirst(m_map, key, value);
}


void InMemoryPerProcess::del(const std::string& key) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)
    m_map.erase(key);
}

void InMemoryPerProcess::delIfExpired(const std::string& key) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)
    // Double check the status while within the mutex
    const auto iter = std::find_if(m_map.begin(), m_map.end(),
        [&key](const auto &x) { return x.first == key && x.second.isExpired(); });
    if (iter != m_map.end()) {
        m_map.erase(key);
    }
}

void InMemoryPerProcess::setExpiry(const std::string& key, int32_t expiry_seconds) {
    const std::lock_guard lock(m_mutex); // write lock (exclusive access)

    if (const auto search = m_map.find(key); search != m_map.end()) {
        search->second.setExpiry(expiry_seconds);
        return;
    }

    // We allow an expiry value to be set for a key that has not (yet) had a value set.
    const auto iter = m_map.emplace(key, CollectionData());
    iter->second.setExpiry(expiry_seconds);
}


void InMemoryPerProcess::resolveSingleMatch(const std::string& var,
    std::vector<const VariableValue *> *l) {
    std::list<std::string> expiredVars;

    {
        const std::shared_lock lock(m_mutex); // read lock (shared access)

        const auto range = m_map.equal_range(var);
        for (auto it = range.first; it != range.second; ++it) {
            if (it->second.isExpired()) {
                expiredVars.push_back(it->first);
            } else if (it->second.hasValue() == false) {
                // No-op. A non-expired expiry exists for the key but there is no actual value
            } else {
                l->push_back(new VariableValue(&m_name, &it->first, &it->second.getValue()));
            }
        }
    }

    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
}


void InMemoryPerProcess::resolveMultiMatches(const std::string& var,
    std::vector<const VariableValue *> *l, variables::KeyExclusions &ke) {
    const auto keySize = var.size();
    l->reserve(15);
    std::list<std::string> expiredVars;

    {
        const std::shared_lock lock(m_mutex); // read lock (shared access)

        if (keySize == 0) {
            for (auto &i : m_map) {
                if (ke.toOmit(i.first)) {
                    continue;
                }
                if (i.second.isExpired()) {
                    expiredVars.push_back(i.first);
                } else if (i.second.hasValue() == false) {
                    // No-op. A non-expired expiry exists for the key but there is no actual value
                } else {
                    l->insert(l->begin(), new VariableValue(&m_name, &i.first,
                        &i.second.getValue()));
                }
            }
        } else {
            const auto range = m_map.equal_range(var);
            for (auto it = range.first; it != range.second; ++it) {
                if (ke.toOmit(var)) {
                    continue;
                }
                if (it->second.isExpired()) {
                    expiredVars.push_back(it->first);
                } else if (it->second.hasValue() == false) {
                    // No-op. A non-expired expiry exists for the key but there is no actual value
                } else {
                    l->insert(l->begin(), new VariableValue(&m_name, &var,
                        &it->second.getValue()));
                }
            }
        }
    }

    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
}


void InMemoryPerProcess::resolveRegularExpression(const std::string& var,
    std::vector<const VariableValue *> *l, variables::KeyExclusions &ke) {
    Utils::Regex r(var, true);
    std::list<std::string> expiredVars;

    {
        const std::shared_lock lock(m_mutex); // read lock (shared access)

        for (const auto& x : m_map) {
            const auto ret = Utils::regex_search(x.first, r);
            if (ret <= 0) {
                continue;
            }
            if (ke.toOmit(x.first)) {
                continue;
            }
            if (x.second.isExpired()) {
                expiredVars.push_back(x.first);
            } else if (x.second.hasValue() == false) {
                // No-op. A non-expired expiry exists for the key but there is no actual value
            } else {
                l->insert(l->begin(), new VariableValue(&m_name, &x.first, &x.second.getValue()));
            }
        }
    }

    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
}


std::unique_ptr<std::string> InMemoryPerProcess::resolveFirst(
    const std::string& var) {
    std::unique_ptr<std::string> ret;
    std::list<std::string> expiredVars;

    {
        const std::shared_lock lock(m_mutex); // read lock (shared access)

        const auto range = m_map.equal_range(var);
        for (auto it = range.first; it != range.second; ++it) {
            if (it->second.isExpired()) {
                expiredVars.push_back(it->first);
            } else if (it->second.hasValue() == false) {
                // No-op. A non-expired expiry exists for the key but there is no actual value
            } else {
                ret = std::make_unique<std::string>(it->second.getValue());
            }
        }
    }

    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }

    return ret;
}


}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
