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

#include "src/operators/pm.h"

#include <algorithm>
#include <iterator>
#include <sstream>

#include "src/utils/acmp.h"
#include "src/utils/string.h"

using namespace modsecurity::utils::string;

static inline std::string parse_pm_content(const std::string &op_parm) {
    auto offset = op_parm.find_first_not_of(" \t");
    if (offset == std::string::npos) {
        return op_parm;
    }

    auto size = op_parm.size() - offset;
    if (size >= 2 &&
        op_parm.at(offset) == '\"' && op_parm.back() == '\"') {
        offset++;
        size -= 2;
    }

    if (size == 0) {
        return op_parm;
    }

    std::string parsed_parm(op_parm.c_str() + offset, size);

    unsigned char bin_offset = 0;
    unsigned char bin_parm[3] = { 0 };
    bool bin = false, esc = false;

    char *d = parsed_parm.data();
    for(const char *s = d, *e = d + size; s != e; ++s) {
        if (*s == '|') {
            bin = !bin;
        } else if(!esc && *s == '\\') {
            esc = true;
        } else {
            if (bin) {
                if (VALID_HEX(*s)) {
                    bin_parm[bin_offset] = (char)*s;
                    bin_offset++;
                    if (bin_offset == 2) {
                        unsigned char c = strtol((char *)bin_parm, (char **) nullptr, 16) & 0xFF;
                        bin_offset = 0;
                        *d++ = c;
                    }
                } else {
                    // Invalid hex character
                    return op_parm;
                }
            } else if (esc) {
                if (*s == ':' ||
                        *s == ';' ||
                        *s == '\\' ||
                        *s == '\"')
                {
                    *d++ = *s;
                } else {
                    // Unsupported escape sequence
                    return op_parm;
                }
                esc = false;
            } else {
                *d++ = *s;
            }
        }
    }

    parsed_parm.resize(d - parsed_parm.c_str());
    return parsed_parm;
}


namespace modsecurity {
namespace operators {

Pm::~Pm() {
    acmp_node_t *root = m_p->root_node;

    cleanup(root);

    free(m_p);
    m_p = NULL;
}


void Pm::cleanup(acmp_node_t *n) {
    if (n == NULL) {
        return;
    }

    cleanup(n->sibling);
    cleanup(n->child);

    postOrderTraversal(n->btree);

    if (n->text && strlen(n->text) > 0) {
        free(n->text);
        n->text = NULL;
    }

    if (n->pattern && strlen(n->pattern) > 0) {
        free(n->pattern);
        n->pattern = NULL;
    }

    free(n);
}


void Pm::postOrderTraversal(acmp_btree_node_t *node) {
    if (node == NULL) {
        return;
    }

    postOrderTraversal(node->right);
    postOrderTraversal(node->left);

    free(node);
}


bool Pm::evaluate(Transaction *transaction, RuleWithActions *rule,
    const std::string &input, std::shared_ptr<RuleMessage> ruleMessage) {
    int rc;
    ACMPT pt;
    pt.parser = m_p;
    pt.ptr = NULL;
    const char *match = NULL;
    rc = acmp_process_quick(&pt, &match, input.c_str(), input.length());

    if (rc >= 0 && transaction) {
        std::string match_(match?match:"");
        logOffset(ruleMessage, rc - match_.size() + 1, match_.size());
        transaction->m_matched.push_back(match_);

        if (rule && rule->hasCaptureAction()) {
            transaction->m_collections.m_tx_collection->storeOrUpdateFirst("0",
                match_);
            ms_dbg_a(transaction, 7, "Added pm match TX.0: " + \
                match_);
        }
    }

    return rc >= 0;
}


bool Pm::init(const std::string &file, std::string *error) {
    const auto op_parm = parse_pm_content(m_param);

    std::istringstream iss{op_parm};
    std::for_each(std::istream_iterator<std::string>(iss),
        std::istream_iterator<std::string>(),
        [this](const auto &a) {
            acmp_add_pattern(m_p, a.c_str(), NULL, NULL, a.length());
        });

    while (m_p->is_failtree_done == 0) {
        acmp_prepare(m_p);
    }

    return true;
}


}  // namespace operators
}  // namespace modsecurity
