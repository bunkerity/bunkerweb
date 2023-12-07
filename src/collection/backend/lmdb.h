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


/**
 * The MDBEnvProvider class defines the `GetInstance` method that serves as an
 * alternative to constructor and lets clients access the same instance of this
 * class over and over. Its used to provide single MDB_env instance for each collection
 * that uses lmdb to store and retrieve data. That approach satisfies lmdb requirement:
 *
 *   "LMDB uses POSIX locks on files, and these locks have issues if one process opens
 *    a file multiple times. Because of this, do not mdb_env_open() a file multiple
 *    times from a single process."
 *
 * Creation of MDB_env is delayed to moment when first transaction is opened.
 * This approach prevents passing env object to forked processes.
 * In that way next lmdb requirement be satisfied:
 *
 *   "Use an MDB_env* in the process which opened it, without fork()ing."
 */
class MDBEnvProvider {

 public:
    MDBEnvProvider(MDBEnvProvider &other) = delete;
    void operator=(const MDBEnvProvider &) = delete;

    /**
     * This is the static method that controls the access to the singleton
     * instance. On the first run, it creates a singleton object and places it
     * into the static field. On subsequent runs, it returns the client existing
     * object stored in the static field (Meyers Singleton implementation).
     */
    static MDBEnvProvider& GetInstance() {
        static MDBEnvProvider instance;
        return instance;
    }
    MDB_env* GetEnv();
    MDB_dbi* GetDBI();
    bool isValid();

    ~MDBEnvProvider();
 private:
    MDB_env *m_env;
    MDB_dbi m_dbi;
    bool valid;

    MDBEnvProvider();
};

class LMDB :
    public Collection {
 public:
    explicit LMDB(const std::string &name);

    bool storeOrUpdateFirst(const std::string &key,
        const std::string &value) override;

    bool updateFirst(const std::string &key,
        const std::string &value) override;

    void del(const std::string& key) override;

    void setExpiry(const std::string& key, int32_t expiry_seconds) override;

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
    int txn_begin(unsigned int flags, MDB_txn **ret);
    void string2val(const std::string& str, MDB_val *val);
    void inline lmdb_debug(int rc, const std::string &op, const std::string &scope);

    void delIfExpired(const std::string& key);

    MDB_env *m_env;
    MDB_dbi m_dbi;
    bool isOpen;
};

}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
#endif

#endif  // WITH_LMDB

#endif  // SRC_COLLECTION_BACKEND_LMDB_H_
