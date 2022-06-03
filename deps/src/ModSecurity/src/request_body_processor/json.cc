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


#ifdef WITH_YAJL

#include "src/request_body_processor/json.h"

#include <list>
#include <iostream>
#include <string>


namespace modsecurity {
namespace RequestBodyProcessor {

JSON::JSON(Transaction *transaction) : m_transaction(transaction),
    m_handle(NULL),
    m_current_key("") {
    /**
     * yajl callback functions
     * For more information on the function signatures and order, check
     * http://lloyd.github.com/yajl/yajl-1.0.12/structyajl__callbacks.html
     */

    /**
     * yajl configuration and callbacks
     */
    static yajl_callbacks callbacks = {
        yajl_null,
        yajl_boolean,
        NULL /* yajl_integer  */,
        NULL /* yajl_double */,
        yajl_number,
        yajl_string,
        yajl_start_map,
        yajl_map_key,
        yajl_end_map,
        yajl_start_array,
        yajl_end_array
    };


    /**
     * yajl initialization
     *
     * yajl_parser_config definition:
     * http://lloyd.github.io/yajl/yajl-2.0.1/yajl__parse_8h.html#aec816c5518264d2ac41c05469a0f986c
     *
     * TODO: make UTF8 validation optional, as it depends on Content-Encoding
     */
    m_handle = yajl_alloc(&callbacks, NULL, this);

    yajl_config(m_handle, yajl_allow_partial_values, 0);
}


JSON::~JSON() {
    while (m_containers.size() > 0) {
        JSONContainer *a = m_containers.back();
        m_containers.pop_back();
        delete a;
    }
    yajl_free(m_handle);
}


bool JSON::init() {
    return true;
}


bool JSON::processChunk(const char *buf, unsigned int size, std::string *err) {
    /* Feed our parser and catch any errors */
    m_status = yajl_parse(m_handle,
        (const unsigned char *)buf, size);
    if (m_status != yajl_status_ok) {
        unsigned char *e = yajl_get_error(m_handle, 0,
            (const unsigned char *)buf, size);
        /* We need to free the yajl error message later, how to do this? */
        err->assign((const char *)e);
        yajl_free_error(m_handle, e);
        return false;
    }

    return true;
}


bool JSON::complete(std::string *err) {
    /* Wrap up the parsing process */
    m_status = yajl_complete_parse(m_handle);
    if (m_status  != yajl_status_ok) {
        unsigned char *e = yajl_get_error(m_handle, 0, NULL, 0);
        /* We need to free the yajl error message later, how to do this? */
        err->assign((const char *)e);
        yajl_free_error(m_handle, e);
        return false;
    }

    return true;
}


int JSON::addArgument(const std::string& value) {
    std::string data("");
    std::string path;

    for (size_t i =  0; i < m_containers.size(); i++) {
        JSONContainerArray *a = dynamic_cast<JSONContainerArray *>(
            m_containers[i]);
        path = path + m_containers[i]->m_name;
        if (a != NULL) {
            path = path + ".array_" + std::to_string(a->m_elementCounter);
        } else {
            path = path + ".";
        }
    }

    if (m_containers.size() > 0) {
        JSONContainerArray *a = dynamic_cast<JSONContainerArray *>(
            m_containers.back());
        if (a) {
            a->m_elementCounter++;
        } else {
            data = getCurrentKey();
        }
    } else {
        data = getCurrentKey();
    }


    m_transaction->addArgument("JSON", path + data, value, 0);

    return 1;
}


/**
 * Callback for hash key values; we use those to define the variable names
 * under ARGS. Whenever we reach a new key, we update the current key value.
 */
int JSON::yajl_map_key(void *ctx, const unsigned char *key, size_t length) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    std::string safe_key;

    /**
     * yajl does not provide us with null-terminated strings, but
     * rather expects us to copy the data from the key up to the
     * length informed; we create a standalone null-termined copy
     * in safe_key
     */
    safe_key.assign((const char *)key, length);

    tthis->m_current_key = safe_key;

    return 1;
}


/**
 * Callback for null values
 *
 */
int JSON::yajl_null(void *ctx) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    return tthis->addArgument("");
}


/**
 * Callback for boolean values
 */
int JSON::yajl_boolean(void *ctx, int value) {
    JSON *tthis =  reinterpret_cast<JSON *>(ctx);
    if (value) {
        return tthis->addArgument("true");
    }
    return tthis->addArgument("false");
}


/**
 * Callback for string values
 */
int JSON::yajl_string(void *ctx, const unsigned char *value, size_t length) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    std::string v = std::string((const char*)value, length);
    return tthis->addArgument(v);
}


/**
 * Callback for numbers; YAJL can use separate callbacks for integers/longs and
 * float/double values, but since we are not interested in using the numeric
 * values here, we use a generic handler which uses numeric strings
 */
int JSON::yajl_number(void *ctx, const char *value, size_t length) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    std::string v = std::string((const char*)value, length);
    return tthis->addArgument(v);
}


/**
 * Callback for a new hash, which indicates a new subtree, labeled as the
 * current argument name, is being created
 */
int JSON::yajl_start_array(void *ctx) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    std::string name = tthis->getCurrentKey();
    tthis->m_containers.push_back(
        reinterpret_cast<JSONContainer *>(new JSONContainerArray(name)));
    return 1;
}


int JSON::yajl_end_array(void *ctx) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    if (tthis->m_containers.size() <= 0) {
        return 1;
    }

    JSONContainer *a = tthis->m_containers.back();
    tthis->m_containers.pop_back();
    delete a;
    if (tthis->m_containers.size() > 0) {
        JSONContainerArray *a = dynamic_cast<JSONContainerArray *>(
            tthis->m_containers.back());
        if (a) {
            a->m_elementCounter++;
        }
    }

    return 1;
}


int JSON::yajl_start_map(void *ctx) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    std::string name(tthis->getCurrentKey());
    tthis->m_containers.push_back(
        reinterpret_cast<JSONContainer *>(new JSONContainerMap(name)));
    return 1;
}


/**
 * Callback for end hash, meaning the current subtree is being closed, and that
 * we should go back to the parent variable label
 */
int JSON::yajl_end_map(void *ctx) {
    JSON *tthis = reinterpret_cast<JSON *>(ctx);
    if (tthis->m_containers.size() <= 0) {
        return 1;
    }

    JSONContainer *a = tthis->m_containers.back();
    tthis->m_containers.pop_back();
    delete a;

    if (tthis->m_containers.size() > 0) {
        JSONContainerArray *a = dynamic_cast<JSONContainerArray *>(
            tthis->m_containers.back());
        if (a) {
            a->m_elementCounter++;
        }
    }

    return 1;
}


}  // namespace RequestBodyProcessor
}  // namespace modsecurity


#endif  // WITH_YAJL

