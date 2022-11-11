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
#include <cstring>
#include <iostream>
#include <unordered_map>
#include <list>
#include <vector>
#include <algorithm>
#include <memory>
#endif

#ifdef WITH_LMDB
#include <lmdb.h>
#include <semaphore.h>
#endif  // WITH_LMDB
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <pthread.h>

#include "modsecurity/variable_value.h"
#include "modsecurity/collection/collection.h"
#include "src/variables/variable.h"

#ifndef SRC_COLLECTION_BACKEND_LMDB_H_
#define SRC_COLLECTION_BACKEND_LMDB_H_

#ifdef WITH_LMDB

#ifdef __cplusplus
namespace modsecurity {
namespace collection {
namespace backend {

class LMDB :
    public Collection {
 public:
    explicit LMDB(std::string name);
    ~LMDB();
    void store(std::string key, std::string value) override;

    bool storeOrUpdateFirst(const std::string &key,
        const std::string &value) override;

    bool updateFirst(const std::string &key,
        const std::string &value) override;

    void del(const std::string& key) override;

    std::unique_ptr<std::string> resolveFirst(const std::string& var) override;

    void resolveSingleMatch(const std::string& var,
        std::vector<const VariableValue *> *l) override;
    void resolveMultiMatches(const std::string& var,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) override;
    void resolveRegularExpression(const std::string& var,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) override;

 private:
    void string2val(const std::string& str, MDB_val *val);
    void inline lmdb_debug(int rc, std::string op, std::string scope);

    MDB_env *m_env;
};

}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
#endif

#endif  // WITH_LMDB

#endif  // SRC_COLLECTION_BACKEND_LMDB_H_
