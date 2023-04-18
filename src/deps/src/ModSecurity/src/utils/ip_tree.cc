/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2022 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/utils/ip_tree.h"

#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string>

#include <fstream>
#include <iostream>

#include "src/utils/geo_lookup.h"
#include "src/utils/https_client.h"

namespace modsecurity {
namespace Utils {

void IpTree::postOrderTraversal(TreeNode *node) {
    if (node == NULL) {
        return;
    }

    postOrderTraversal(node->left);
    postOrderTraversal(node->right);

    if (node->netmasks) {
        free(node->netmasks);
        node->netmasks = NULL;
    }
    if (node->prefix) {
        if (node->prefix->buffer) {
            free(node->prefix->buffer);
            node->prefix->buffer = NULL;
        }
        if (node->prefix->prefix_data) {
            free(node->prefix->prefix_data);
            node->prefix->prefix_data = NULL;
        }
        free(node->prefix);
        node->prefix = NULL;
    }
    free(node);
}


IpTree::IpTree() {
    // FIXME: deal with possible error.
    char *error;
    create_radix_tree(&m_tree, &error);
}


IpTree::~IpTree() {
    if (m_tree != NULL) {
        if (m_tree->ipv4_tree != NULL) {
            // Tree_traversal: Post-order to delete all the items.
            postOrderTraversal(m_tree->ipv4_tree->head);
            free(m_tree->ipv4_tree);
            m_tree->ipv4_tree = NULL;
        }
        if (m_tree->ipv6_tree != NULL) {
            // Tree_traversal: Post-order to delete all the items.
            postOrderTraversal(m_tree->ipv6_tree->head);
            free(m_tree->ipv6_tree);
            m_tree->ipv6_tree = NULL;
        }

        free(m_tree);
        m_tree = NULL;
    }
}

bool IpTree::addFromBuffer(std::istream *ss, std::string *error) {
    char *error_msg = NULL;
    for (std::string line; std::getline(*ss, line); ) {
        size_t comment_start = line.find('#');
        if (comment_start != std::string::npos) {
            line = line.substr(0, comment_start);
        }
        int res = add_ip_from_param(line.c_str(), &m_tree, &error_msg);
        if (res != 0) {
            if (error_msg != NULL) {
                error->assign(error_msg);
            }
            return false;
        }
    }

    return true;
}


bool IpTree::addFromBuffer(const std::string& buffer, std::string *error) {
    std::stringstream ss;
    ss << buffer;
    return addFromBuffer(&ss, error);
}


bool IpTree::addFromFile(const std::string& file, std::string *error) {
    std::ifstream myfile(file, std::ios::in);

    if (myfile.is_open() == false) {
        error->assign("Failed to open file: " + file);
        return false;
    }

    return addFromBuffer(&myfile, error);
}


bool IpTree::addFromUrl(const std::string& url, std::string *error) {
    HttpsClient c;
    bool ret = c.download(url);

    if (ret == false) {
        error->assign(c.error);
    } else {
        ret = addFromBuffer(c.content, error);
    }

    return ret;
}


bool IpTree::contains(const std::string& ip) {
    int res = 0;
    char *error_msg = NULL;

    res = tree_contains_ip(m_tree, ip.c_str(), &error_msg);

    if (res < 0) {
        return false;
    }

    if (res > 0) {
        return true;
    }

    return false;
}


}  // namespace Utils
}  // namespace modsecurity
