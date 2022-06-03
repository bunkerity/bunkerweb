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

#include "src/operators/fuzzy_hash.h"

#include <string>

#include "src/operators/operator.h"
#include "src/utils/system.h"

namespace modsecurity {
namespace operators {

bool FuzzyHash::init(const std::string &param2, std::string *error) {
#ifdef WITH_SSDEEP
    std::string digit;
    std::string file;
    std::istream *iss;
    struct fuzzy_hash_chunk *chunk, *t;
    std::string err;

    auto pos = m_param.find_last_of(' ');
    if (pos == std::string::npos) {
        error->assign("Please use @fuzzyHash with filename and value");
        return false;
    }
    digit.append(std::string(m_param, pos+1));
    file.append(std::string(m_param, 0, pos));
    try {
        m_threshold = std::stoi(digit);
    } catch (...) {
        error->assign("Expecting a digit, got: " + digit);
        return false;
    }

    std::string resource = utils::find_resource(file, param2, &err);
    iss = new std::ifstream(resource, std::ios::in);

    if (((std::ifstream *)iss)->is_open() == false) {
        error->assign("Failed to open file: " + m_param + ". " + err);
        delete iss;
        return false;
    }

    for (std::string line; std::getline(*iss, line); ) {
       chunk = (struct fuzzy_hash_chunk *)calloc(1,
            sizeof(struct fuzzy_hash_chunk));

        chunk->data = strdup(line.c_str());
        chunk->next = NULL;

        if (m_head == NULL) {
            m_head = chunk;
        } else {
            t = m_head;

            while (t->next) {
                t = t->next;
            }

            t->next = chunk;
        }
    }

    delete iss;
    return true;
#else
    error->assign("@fuzzyHash: SSDEEP support was not enabled " \
        "during the compilation.");
    return false;
#endif
}

FuzzyHash::~FuzzyHash() {
    struct fuzzy_hash_chunk *c = m_head;
    while (c) {
        struct fuzzy_hash_chunk *t = c;
        free(c->data);
        c->data = NULL;
        c = c->next;
        free(t);
    }
    m_head = NULL;
}


bool FuzzyHash::evaluate(Transaction *t, const std::string &str) {
#ifdef WITH_SSDEEP
    char result[FUZZY_MAX_RESULT];
    struct fuzzy_hash_chunk *chunk = m_head;

    if (fuzzy_hash_buf((const unsigned char*)str.c_str(),
        str.size(), result)) {
        ms_dbg_a(t, 4, "Problems generating fuzzy hash");
        return false;
    }

    while (chunk != NULL) {
        int i = fuzzy_compare(chunk->data, result);
        if (i >= m_threshold) {
            ms_dbg_a(t, 4, "Fuzzy hash: matched " \
                "with score: " + std::to_string(i) + ".");
            return true;
        }
        chunk = chunk->next;
    }
#endif
    /* No match. */
    return false;
}

}  // namespace operators
}  // namespace modsecurity
