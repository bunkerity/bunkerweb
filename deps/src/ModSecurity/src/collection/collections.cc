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


#include "modsecurity/collection/collections.h"

#ifdef __cplusplus
#include <string>
#include <iostream>
#include <unordered_map>
#include <list>
#include <vector>
#endif

#include "modsecurity/variable_value.h"
#include "modsecurity/collection/collection.h"
#include "src/collection/backend/in_memory-per_process.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace collection {


Collections::Collections(Collection *global,
    Collection *ip, Collection *session, Collection *user,
    Collection *resource) : m_global_collection_key(""),
    m_ip_collection_key(""),
    m_resource_collection_key(""),
    m_global_collection(global),
    m_resource_collection(resource),
    m_ip_collection(ip),
    m_session_collection(session),
    m_user_collection(user),
    m_tx_collection(new backend::InMemoryPerProcess("TX")) {
    }


Collections::~Collections() {
    delete m_tx_collection;
}


}  // namespace collection
}  // namespace modsecurity
