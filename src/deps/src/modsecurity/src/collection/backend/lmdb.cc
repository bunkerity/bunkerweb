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


#include "src/collection/backend/lmdb.h"
#include "src/collection/backend/collection_data.h"

#include <sys/types.h>
#include <unistd.h>

#include <string>
#include <memory>

#include <pthread.h>

#include "modsecurity/variable_value.h"
#include "src/utils/regex.h"
#include "src/variables/variable.h"

#undef LMDB_STDOUT_COUT

namespace modsecurity {
namespace collection {
namespace backend {


#ifdef WITH_LMDB

LMDB::LMDB(const std::string &name) :
    Collection(name), m_env(NULL), isOpen(false) {}

int LMDB::txn_begin(unsigned int flags, MDB_txn **ret) {
    if (!isOpen) {
        m_env = MDBEnvProvider::GetInstance().GetEnv();
        m_dbi = *(MDBEnvProvider::GetInstance().GetDBI());
        isOpen = true;
    }

    if (MDBEnvProvider::GetInstance().isValid()) {
        return mdb_txn_begin(m_env, NULL, flags, ret);
    } else {
        return -1;
    }
}

void LMDB::string2val(const std::string& str, MDB_val *val) {
    val->mv_size = sizeof(char)*(str.size());
    val->mv_data = const_cast<char *>(str.c_str());
}


void LMDB::lmdb_debug(int rc, const std::string &op, const std::string &scope) {
#ifndef LMDB_STDOUT_COUT
    return;
#else
    if (rc == 0) {
        return;
    }

    if (op == "txn") {
        std::cout << scope << ", LMDB failure while starting txn: ";
        switch (rc) {
            case MDB_PANIC:
                std::cout << "panic: a fatal error occurred earlier ";
                std::cout << "and the environment must be shut down.";
                break;
            case MDB_MAP_RESIZED:
                std::cout << "map resized: another process wrote data ";
                std::cout << "beyond this MDB_env's mapsize and this ";
                std::cout << "environment's map must be resized as well. ";
                std::cout << "See mdb_env_set_mapsize().";
                break;
            case MDB_READERS_FULL:
                std::cout << "max readers: a read-only transaction was ";
                std::cout << "requested and the reader lock table is full. ";
                std::cout << "See mdb_env_set_maxreaders().";
                break;
            case ENOMEM:
                std::cout << "out of memory.";
                break;
            default:
                std::cout << "not sure what is wrong, code: " +
                    std::to_string(rc);
                break;
        }
        std::cout << std::endl;
    } else if (op == "get") {
        std::cout << scope << ", LMDB failure while getting the key: ";
        switch (rc) {
            case MDB_NOTFOUND:
                std::cout << "not found: the key was not in the database.";
                break;
            case EINVAL:
                std::cout << "an invalid parameter was specified.";
                break;
            default:
                std::cout << "not sure what is wrong.";
                break;
        }
        std::cout << std::endl;
    } else if (op == "del") {
        std::cout << scope << ", delete procedure failed: ";
        switch (rc) {
            case EACCES:
                std::cout << "an attempt was made to write in a ";
                std::cout << "read-only transaction.";
                break;
            case EINVAL:
                std::cout << "an invalid parameter was specified.";
                break;
            default:
                std::cout << "not sure what is wrong. Code: " +
                std::to_string(rc);
                break;
        }
        std::cout << std::endl;
    } else if (op == "commit") {
        std::cout << scope << ", commit procedure failed: ";
        switch (rc) {
            case EINVAL:
                std::cout << "an invalid parameter was specified.";
                break;
            case ENOSPC:
                std::cout << "no more disk space.";
                break;
            case EIO:
                std::cout << "a low-level I/O error occurred while writing.";
                break;
            case ENOMEM:
                std::cout << "out of memory.";
                break;
            default:
                std::cout << "not sure what is wrong. Code: " +
                    std::to_string(rc);
                break;
        }
        std::cout << std::endl;
    }
#endif
}


std::unique_ptr<std::string> LMDB::resolveFirst(const std::string& var) {
    int rc;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    std::unique_ptr<std::string> ret = NULL;
    MDB_txn *txn = NULL;
    CollectionData collectionData;

    string2val(var, &mdb_key);

    rc = txn_begin(MDB_RDONLY, &txn);
    lmdb_debug(rc, "txn", "resolveFirst");
    if (rc != 0) {
        goto end_txn;
    }
    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "resolveFirst");
    if (rc != 0) {
        goto end_get;
    }

    collectionData.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
    if ((!collectionData.isExpired()) && (collectionData.hasValue())) {
        ret = std::unique_ptr<std::string>(new std::string(collectionData.getValue()));
    }

end_get:
    mdb_txn_abort(txn);
end_txn:
    // The read-only transaction is complete. Now we can do a delete if the item was expired.
    if (collectionData.isExpired()) {
        delIfExpired(var);
    }
    return ret;
}


void LMDB::setExpiry(const std::string &key, int32_t expiry_seconds) {
    int rc;
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    CollectionData previous_data;
    CollectionData new_data;
    std::string serializedData;

    string2val(key, &mdb_key);

    rc = txn_begin(0, &txn);
    lmdb_debug(rc, "txn", "setExpiry");
    if (rc != 0) {
        goto end_txn;
    }

    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "setExpiry");
    if (rc == 0) {
        previous_data.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
        rc = mdb_del(txn, m_dbi, &mdb_key, &mdb_value_ret);
        lmdb_debug(rc, "del", "setExpiry");
        if (rc != 0) {
            goto end_del;
        }
    }

    if (previous_data.hasValue()) {
        new_data = previous_data;
    };
    new_data.setExpiry(expiry_seconds);
    serializedData = new_data.getSerialized();
    string2val(serializedData, &mdb_value);

    rc = mdb_put(txn, m_dbi, &mdb_key, &mdb_value, 0);
    lmdb_debug(rc, "put", "setExpiry");
    if (rc != 0) {
        goto end_put;
    }

    rc = mdb_txn_commit(txn);
    lmdb_debug(rc, "commit", "setExpiry");
    if (rc != 0) {
        goto end_commit;
    }

end_put:
end_del:
    if (rc != 0) {
        mdb_txn_abort(txn);
    }
end_commit:
end_txn:
    return;
}

void LMDB::delIfExpired(const std::string& key) {
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value_ret;
    CollectionData collectionData;

    int rc = txn_begin(0, &txn);
    lmdb_debug(rc, "txn", "del");
    if (rc != 0) {
        goto end_txn;
    }

    string2val(key, &mdb_key);

    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "del");
    if (rc != 0) {
        goto end_get;
    }

    collectionData.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
    if (collectionData.isExpired()) {
        rc = mdb_del(txn, m_dbi, &mdb_key, &mdb_value_ret);
        lmdb_debug(rc, "del", "del");
        if (rc != 0) {
            goto end_del;
        }
    }

    rc = mdb_txn_commit(txn);
    lmdb_debug(rc, "commit", "del");
    if (rc != 0) {
        goto end_commit;
    }

end_del:
end_get:
    if (rc != 0) {
        mdb_txn_abort(txn);
    }
end_commit:
end_txn:
    return;
}

bool LMDB::storeOrUpdateFirst(const std::string &key,
    const std::string &value) {
    int rc;
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    CollectionData previous_data;
    CollectionData new_data;
    std::string serializedData;

    string2val(key, &mdb_key);

    rc = txn_begin(0, &txn);
    lmdb_debug(rc, "txn", "storeOrUpdateFirst");
    if (rc != 0) {
        goto end_txn;
    }

    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "storeOrUpdateFirst");
    if (rc == 0) {
        previous_data.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
        rc = mdb_del(txn, m_dbi, &mdb_key, &mdb_value_ret);
        lmdb_debug(rc, "del", "storeOrUpdateFirst");
        if (rc != 0) {
            goto end_del;
        }
    }

    if (previous_data.hasExpiry()) {
        new_data = previous_data;
    };
    new_data.setValue(value);
    serializedData = new_data.getSerialized();
    string2val(serializedData, &mdb_value);

    rc = mdb_put(txn, m_dbi, &mdb_key, &mdb_value, 0);
    lmdb_debug(rc, "put", "storeOrUpdateFirst");
    if (rc != 0) {
        goto end_put;
    }

    rc = mdb_txn_commit(txn);
    lmdb_debug(rc, "commit", "storeOrUpdateFirst");
    if (rc != 0) {
        goto end_commit;
    }

end_put:
end_del:
    if (rc != 0) {
        mdb_txn_abort(txn);
    }
end_commit:
end_txn:
    return true;
}


void LMDB::resolveSingleMatch(const std::string& var,
    std::vector<const VariableValue *> *l) {
    int rc;
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    MDB_cursor *cursor;
    CollectionData collectionData;
    std::list<std::string> expiredVars;

    rc = txn_begin(MDB_RDONLY, &txn);
    lmdb_debug(rc, "txn", "resolveSingleMatch");
    if (rc != 0) {
        goto end_txn;
    }

    string2val(var, &mdb_key);

    mdb_cursor_open(txn, m_dbi, &cursor);
    while ((rc = mdb_cursor_get(cursor, &mdb_key,
            &mdb_value_ret, MDB_NEXT_DUP)) == 0) {
        collectionData.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
        if (collectionData.isExpired()) {
            expiredVars.push_back(std::string(reinterpret_cast<char *>(mdb_key.mv_data), mdb_key.mv_size));
            continue;
        }
        if (!collectionData.hasValue()) {
            continue;
        }
        VariableValue *v = new VariableValue(&var, &collectionData.getValue());
        l->push_back(v);
    }

    mdb_cursor_close(cursor);
    mdb_txn_abort(txn);
end_txn:
    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
    return;
}


bool LMDB::updateFirst(const std::string &key,
    const std::string &value) {
    int rc;
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    CollectionData previous_data;
    CollectionData new_data;
    std::string serializedData;

    rc = txn_begin(0, &txn);
    lmdb_debug(rc, "txn", "updateFirst");
    if (rc != 0) {
        goto end_txn;
    }

    string2val(key, &mdb_key);

    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "updateFirst");
    if (rc != 0) {
        goto end_get;
    }

    previous_data.setFromSerialized(reinterpret_cast<char *>(mdb_value_ret.mv_data), mdb_value_ret.mv_size);
    rc = mdb_del(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "del", "updateFirst");
    if (rc != 0) {
        goto end_del;
    }

    if (previous_data.hasExpiry()) {
        new_data = previous_data;
    };
    new_data.setValue(value);
    serializedData = new_data.getSerialized();
    string2val(serializedData, &mdb_value);

    rc = mdb_put(txn, m_dbi, &mdb_key, &mdb_value, 0);
    lmdb_debug(rc, "put", "updateFirst");
    if (rc != 0) {
        goto end_put;
    }

    rc = mdb_txn_commit(txn);
    lmdb_debug(rc, "commit", "updateFirst");
    if (rc != 0) {
        goto end_commit;
    }

end_put:
end_del:
end_get:
    if (rc != 0) {
        mdb_txn_abort(txn);
    }
end_commit:
end_txn:

    return rc == 0;
}


void LMDB::del(const std::string& key) {
    int rc;
    MDB_txn *txn;
    MDB_val mdb_key;
    MDB_val mdb_value;
    MDB_val mdb_value_ret;
    MDB_stat mst;

    rc = txn_begin(0, &txn);
    lmdb_debug(rc, "txn", "del");
    if (rc != 0) {
        goto end_txn;
    }

    string2val(key, &mdb_key);

    rc = mdb_get(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "get", "del");
    if (rc != 0) {
        goto end_get;
    }

    rc = mdb_del(txn, m_dbi, &mdb_key, &mdb_value_ret);
    lmdb_debug(rc, "del", "del");
    if (rc != 0) {
        goto end_del;
    }

    rc = mdb_txn_commit(txn);
    lmdb_debug(rc, "commit", "del");
    if (rc != 0) {
        goto end_commit;
    }

end_del:
end_get:
    if (rc != 0) {
        mdb_txn_abort(txn);
    }
end_commit:
end_txn:
    return;
}

void LMDB::resolveMultiMatches(const std::string& var,
    std::vector<const VariableValue *> *l,
    variables::KeyExclusions &ke) {
    MDB_val key, data;
    MDB_txn *txn = NULL;
    int rc;
    MDB_stat mst;
    size_t keySize = var.size();
    MDB_cursor *cursor;
    CollectionData collectionData;
    std::list<std::string> expiredVars;

    rc = txn_begin(MDB_RDONLY, &txn);
    lmdb_debug(rc, "txn", "resolveMultiMatches");
    if (rc != 0) {
        goto end_txn;
    }

    rc = mdb_cursor_open(txn, m_dbi, &cursor);
    lmdb_debug(rc, "cursor_open", "resolveMultiMatches");
    if (rc != 0) {
        goto end_cursor_open;
    }

    if (keySize == 0) {
        while ((rc = mdb_cursor_get(cursor, &key, &data, MDB_NEXT)) == 0) {
            collectionData.setFromSerialized(reinterpret_cast<char *>(data.mv_data), data.mv_size);

            if (collectionData.isExpired()) {
                expiredVars.push_back(std::string(reinterpret_cast<char *>(key.mv_data), key.mv_size));
                continue;
            }
            if (!collectionData.hasValue()) {
                continue;
            }

            std::string key_to_insert(reinterpret_cast<char *>(key.mv_data), key.mv_size);
            l->insert(l->begin(), new VariableValue(
                &m_name, &key_to_insert, &collectionData.getValue()));
        }
    } else {
        while ((rc = mdb_cursor_get(cursor, &key, &data, MDB_NEXT)) == 0) {
            collectionData.setFromSerialized(reinterpret_cast<char *>(data.mv_data), data.mv_size);

            if (collectionData.isExpired()) {
                expiredVars.push_back(std::string(reinterpret_cast<char *>(key.mv_data), key.mv_size));
                continue;
            }
            if (!collectionData.hasValue()) {
                continue;
            }

            char *a = reinterpret_cast<char *>(key.mv_data);
            if (strncmp(var.c_str(), a, keySize) == 0) {
                std::string key_to_insert(reinterpret_cast<char *>(key.mv_data), key.mv_size);
                l->insert(l->begin(), new VariableValue(&m_name, &key_to_insert, &collectionData.getValue()));
            }
        }
    }

    mdb_cursor_close(cursor);
end_cursor_open:
    mdb_txn_abort(txn);
end_txn:
    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
    return;
}


void LMDB::resolveRegularExpression(const std::string& var,
    std::vector<const VariableValue *> *l,
    variables::KeyExclusions &ke) {
    MDB_val key, data;
    MDB_txn *txn = NULL;
    int rc;
    MDB_stat mst;
    MDB_cursor *cursor;
    CollectionData collectionData;
    std::list<std::string> expiredVars;

    Utils::Regex r(var, true);

    rc = txn_begin(MDB_RDONLY, &txn);
    lmdb_debug(rc, "txn", "resolveRegularExpression");
    if (rc != 0) {
        goto end_txn;
    }

    rc = mdb_cursor_open(txn, m_dbi, &cursor);
    lmdb_debug(rc, "cursor_open", "resolveRegularExpression");
    if (rc != 0) {
        goto end_cursor_open;
    }

    while ((rc = mdb_cursor_get(cursor, &key, &data, MDB_NEXT)) == 0) {
        collectionData.setFromSerialized(reinterpret_cast<char *>(data.mv_data), data.mv_size);

	if (collectionData.isExpired()) {
            expiredVars.push_back(std::string(reinterpret_cast<char *>(key.mv_data), key.mv_size));
            continue;
        }
        if (!collectionData.hasValue()) {
            continue;
        }

        std::string key_to_insert(reinterpret_cast<char *>(key.mv_data), key.mv_size);
        int ret = Utils::regex_search(key_to_insert, r);
        if (ret <= 0) {
            continue;
        }
        if (ke.toOmit(key_to_insert)) {
            continue;
        }

        VariableValue *v = new VariableValue(&key_to_insert, &collectionData.getValue());
        l->insert(l->begin(), v);
    }

    mdb_cursor_close(cursor);
end_cursor_open:
    mdb_txn_abort(txn);
end_txn:
    for (const auto& expiredVar : expiredVars) {
        delIfExpired(expiredVar);
    }
    return;
}


MDBEnvProvider::MDBEnvProvider() : m_env(NULL), valid(false) {
    int rc;
    MDB_txn *txn;
    mdb_env_create(&m_env);
    rc = mdb_env_open(m_env, "./modsec-shared-collections",
        MDB_WRITEMAP | MDB_NOSUBDIR, 0664);

    if (rc == 0) {
        valid = true;
        mdb_txn_begin(m_env, NULL, 0, &txn);
        mdb_dbi_open(txn, NULL, MDB_CREATE | MDB_DUPSORT, &m_dbi);
        mdb_txn_commit(txn);
    }
}

MDB_env* MDBEnvProvider::GetEnv() {
    return m_env;
}

MDB_dbi* MDBEnvProvider::GetDBI() {
    return &m_dbi;
}

bool MDBEnvProvider::isValid() {
    return valid;
}

MDBEnvProvider::~MDBEnvProvider() {
    mdb_dbi_close(m_env, m_dbi);
    mdb_env_close(m_env);
}

#endif

}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
