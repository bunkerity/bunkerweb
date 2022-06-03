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

#ifndef SRC_REQUEST_BODY_PROCESSOR_JSON_H_
#define SRC_REQUEST_BODY_PROCESSOR_JSON_H_


#ifdef WITH_YAJL

#include <yajl/yajl_parse.h>

#include <string>
#include <iostream>
#include <deque>

#include "modsecurity/transaction.h"
#include "modsecurity/rules.h"



namespace modsecurity {
namespace RequestBodyProcessor {


class JSONContainer {
 public:
    explicit JSONContainer(std::string name) : m_name(name) { }
    virtual ~JSONContainer() { }
    std::string m_name;
};


class JSONContainerArray : public JSONContainer {
 public:
    explicit JSONContainerArray(std::string name) : JSONContainer(name),
        m_elementCounter(0) { }
    size_t m_elementCounter;
};


class JSONContainerMap : public JSONContainer {
 public:
     explicit JSONContainerMap(std::string name) : JSONContainer(name) { }
};


class JSON {
 public:
    explicit JSON(Transaction *transaction);
    ~JSON();

    bool init();
    bool processChunk(const char *buf, unsigned int size, std::string *err);
    bool complete(std::string *err);

    int addArgument(const std::string& value);

    static int yajl_number(void *ctx, const char *value, size_t length);
    static int yajl_string(void *ctx, const unsigned char *value,
        size_t length);
    static int yajl_boolean(void *ctx, int value);
    static int yajl_null(void *ctx);
    static int yajl_map_key(void *ctx, const unsigned char *key,
        size_t length);
    static int yajl_end_map(void *ctx);
    static int yajl_start_map(void *ctx);
    static int yajl_start_array(void *ctx);
    static int yajl_end_array(void *ctx);

    bool isPreviousArray() {
        JSONContainerArray *prev = NULL;
        if (m_containers.size() < 1) {
            return false;
        }
        prev = dynamic_cast<JSONContainerArray *>(
            m_containers[m_containers.size() - 1]);
        return prev != NULL;
    }

    std::string getCurrentKey(bool emptyIsNull = false) {
        std::string ret(m_current_key);
        if (m_containers.size() == 0) {
            return "json";
        }
        if (m_current_key.empty() == true) {
            if (isPreviousArray() || emptyIsNull == true) {
                return "";
            }
            return "empty-key";
        }
        m_current_key = "";
        return ret;
    }

 private:
    std::deque<JSONContainer *> m_containers;
    Transaction *m_transaction;
    yajl_handle m_handle;
    yajl_status m_status;
    std::string m_current_key;
};


}  // namespace RequestBodyProcessor
}  // namespace modsecurity

#endif  // WITH_YAJL

#endif  // SRC_REQUEST_BODY_PROCESSOR_JSON_H_

