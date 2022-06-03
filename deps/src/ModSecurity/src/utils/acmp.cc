/*
* ModSecurity for Apache 2.x, http://www.modsecurity.org/
* Copyright (c) 2004-2013 Trustwave Holdings, Inc. (http://www.trustwave.com/)
*
* You may not use this file except in compliance with
* the License.  You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* If any of the files related to licensing are missing or if you have any
* other questions related to licensing please contact Trustwave Holdings, Inc.
* directly using the email address security@modsecurity.org.
*/

/* Aho-Corasick Matching  */

#include "src/utils/acmp.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cstddef>
#include <stdio.h>
#include <ctype.h>

#include <iostream>
#include <string>
#include <vector>


/**
 * TODO: This code comes from ModSecurity 2.9.0 there are two memory leaks here
 *       that should be mitigated. This ACMP parser should be re-written to
 *       consume less memory.
 */
extern "C" {

char *parse_pm_content(const char *op_parm, unsigned short int op_len, const char **error_msg)  {
    char *parm = NULL;
    char *content;
    unsigned short int offset = 0;
//    char converted = 0;
    int i, x;
    unsigned char bin = 0, esc = 0, bin_offset = 0;
    unsigned char c = 0;
    unsigned char bin_parm[3] = { 0 };
    char *processed = NULL;

    content = strdup(op_parm);

    if (content == NULL) {
        *error_msg = std::string("Error allocating memory for pattern matching content.").c_str();
        return NULL;
    }

    while (offset < op_len && (content[offset] == ' ' || content[offset] == '\t')) {
        offset++;
    };

    op_len = strlen(content);

    if (content[offset] == '\"' && content[op_len-1] == '\"') {
        parm = strdup(content + offset + 1);
        if (parm  == NULL) {
            *error_msg = std::string("Error allocating memory for pattern matching content.").c_str();
            free(content);
            content = NULL;
            return NULL;
        }
        parm[op_len - offset - 2] = '\0';
    } else {
        parm = strdup(content + offset);
        if (parm == NULL) {
            free(content);
            content = NULL;
            *error_msg = std::string("Error allocating memory for pattern matching content.").c_str();
            return NULL;
        }
    }

    free(content);
    content = NULL;

    op_len = strlen(parm);

    if (op_len == 0)   {
        *error_msg = "Content length is 0.";
        free(parm);
        return NULL;
    }

    for (i = 0, x = 0; i < op_len; i++) {
        if (parm[i] == '|') {
            if (bin) {
                bin = 0;
            } else {
                bin = 1;
            }
        } else if(!esc && parm[i] == '\\') {
            esc = 1;
        } else {
            if (bin) {
                if (parm[i] == 0 || parm[i] == 1 || parm[i] == 2 ||
                    parm[i] == 3 || parm[i] == 4 || parm[i] == 5 ||
                    parm[i] == 6 || parm[i] == 7 || parm[i] == 8 ||
                    parm[i] == 9 ||
                    parm[i] == 'A' || parm[i] == 'a' ||
                    parm[i] == 'B' || parm[i] == 'b' ||
                    parm[i] == 'C' || parm[i] == 'c' ||
                    parm[i] == 'D' || parm[i] == 'd' ||
                    parm[i] == 'E' || parm[i] == 'e' ||
                    parm[i] == 'F' || parm[i] == 'f')
                {
                    bin_parm[bin_offset] = (char)parm[i];
                    bin_offset++;
                    if (bin_offset == 2) {
                        c = strtol((char *)bin_parm, (char **) NULL, 16) & 0xFF;
                        bin_offset = 0;
                        parm[x] = c;
                        x++;
                        //converted = 1;
                    }
                } else if (parm[i] == ' ') {
                }
            } else if (esc) {
                if (parm[i] == ':' ||
                        parm[i] == ';' ||
                        parm[i] == '\\' ||
                        parm[i] == '\"')
                {
                    parm[x] = parm[i];
                    x++;
                } else {
                    *error_msg = std::string("Unsupported escape sequence.").c_str();
                    free(parm);
                    return NULL;
                }
                esc = 0;
                //converted = 1;
            } else {
                parm[x] = parm[i];
                x++;
            }
        }
    }

#if 0
    if (converted) {
        op_len = x;
    }
#endif

    //processed = memcpy(processed, parm, op_len);
    processed = strdup(parm);
    free(parm);
    parm = NULL;

    if (processed == NULL) {
        *error_msg = std::string("Error allocating memory for pattern matching content.").c_str();
        return NULL;
    }

    return processed;
}

/*
 *******************************************************************************
 *******************************************************************************
 * Functions for UTF-8 support
 */


/*
 *******************************************************************************
 *******************************************************************************
 * Code for local / static utility functions
 */

/**
 * Returns length of given string for parser's encoding
 */
static size_t acmp_strlen(ACMP *parser, const char *str) {
    return strlen(str);
}

/**
 * Turns string to array of ucs values, depending on parser's encoding
 *       str - string to convert, doesn't have to be NULL-terminated
 * ucs_chars - where to write ucs values
 *       len - length of input string
 */
static void acmp_strtoucs(ACMP *parser, const char *str, long *ucs_chars, int len) {
    int i;
    const char *c = str;

    for (i = 0; i < len; i++) {
        *(ucs_chars++) = *(c++);
    }
}

/**
 * Returns node with given letter, or null if not found
 */
static acmp_node_t *acmp_child_for_code(acmp_node_t *parent_node, long ucs_code) {
    acmp_node_t *node = parent_node->child;
    if (node == NULL) return NULL;
    for (;;) {
        if (node->letter == ucs_code) return node;
        node = node->sibling;
        if (node == NULL) return NULL;
    }
}

/**
 * Adds node to parent node, if it is not already there
 */
static void acmp_add_node_to_parent(acmp_node_t *parent, acmp_node_t *child) {
    acmp_node_t *node = NULL;

    child->parent = parent;
    if (parent->child == NULL) {
        parent->child = child;
        return;
    }

    node = parent->child;
    for (;;) {
        if (node == child) return;
        if (node->sibling == NULL) {
            node->sibling = child;
            return;
        }
        node = node->sibling;
    }
}

/**
 * Copies values from one node to another, without child/sibling/fail pointers
 * and without state variables.
 */
static void acmp_clone_node_no_state(acmp_node_t *from, acmp_node_t *to) {
    memcpy(to, from, sizeof(acmp_node_t));
    to->child = NULL;
    to->sibling = NULL;
    to->fail = NULL;
    to->hit_count = 0;
}

static inline acmp_node_t *acmp_btree_find(acmp_node_t *node, long letter) {
    acmp_btree_node_t *bnode = node->btree;
    for (;;) {
        if (bnode == NULL) return NULL;
        if (bnode->letter == letter) return bnode->node;
        if (bnode->letter > letter) {
            bnode = bnode->left;
        } else {
            bnode = bnode->right;
        }
    }
}

/**
 *
 */
static inline acmp_node_t *acmp_goto(acmp_node_t *node, long letter) {
    return acmp_btree_find(node, letter);
}

/**
 * Connects each node with its first fail node that is end of a phrase.
 */
static void acmp_connect_other_matches(ACMP *parser, acmp_node_t *node) {
    acmp_node_t *child, *om;

    for (child = node->child; child != NULL; child = child->sibling) {
        if (child->fail == NULL) continue;
        for (om = child->fail; om != parser->root_node; om = om->fail) {
            if (om->is_last) {
                child->o_match = om;
                break;
            }
        }
    }

    /* Go recursively through children of this node that have a child node */
    for(child = node->child; child != NULL; child = child->sibling) {
        if (child->child != NULL) acmp_connect_other_matches(parser, child);
    }
}

/**
 * Adds leaves to binary tree, working from sorted array of keyword tree nodes
 */
static void acmp_add_btree_leaves(acmp_btree_node_t *node, acmp_node_t *nodes[],
        int pos, int lb, int rb) {

    int left = 0, right = 0;
    if ((pos - lb) > 1) {
        left = lb + (pos - lb) / 2;
        node->left = reinterpret_cast<acmp_btree_node_t *>(calloc(1, sizeof(acmp_btree_node_t)));
        node->left->node = NULL;
        node->left->right = NULL;
        node->left->left = NULL;
        node->left->letter = 0;
        /* ENH: Check alloc succeded */
        node->left->node = nodes[left];
        node->left->letter = nodes[left]->letter;
#ifdef DEBUG_ACMP
        fprintf(stderr, "%lc ->left %lc\n", (wint_t)node->node->letter, (wint_t)node->left->node->letter);
#endif
    }
    if ((rb - pos) > 1) {
        right = pos + (rb - pos) / 2;
        node->right = reinterpret_cast<acmp_btree_node_t *>(calloc(1, sizeof(acmp_btree_node_t)));
        node->right->node = NULL;
        node->right->right = NULL;
        node->right->left = NULL;
        node->right->letter = 0;
        /* ENH: Check alloc succeded */
        node->right->node = nodes[right];
        node->right->letter = nodes[right]->letter;
#ifdef DEBUG_ACMP
        fprintf(stderr, "%lc ->right %lc\n", (wint_t)node->node->letter, (wint_t)node->right->node->letter);
#endif
    }
    if (node->right != NULL) {
        acmp_add_btree_leaves(node->right, nodes, right, pos, rb);
    }
    if (node->left != NULL) {
        acmp_add_btree_leaves(node->left, nodes, left, lb, pos);
    }
}

/**
 * Builds balanced binary tree from children nodes of given node.
 */
static void acmp_build_binary_tree(ACMP *parser, acmp_node_t *node) {
    size_t count, i, j;
    acmp_node_t *child = node->child;
    acmp_node_t **nodes;
    size_t pos;

    /* Build an array big enough */
    for (count = 0; child != NULL; child = child->sibling) count++;
    nodes = (acmp_node_t **)calloc(1, count * sizeof(acmp_node_t *));
    /* ENH: Check alloc succeded */

    /* ENH: Combine this in the loop below - we do not need two loops */
    child = node->child;
    for (i = 0; i < count; i++) {
        nodes[i] = child;
        child = child->sibling;
    };

    /* We have array with all children of the node and number of those children
     */
    for (i = 0; i < count - 1; i++)
        for (j = i + 1; j < count; j++) {
            acmp_node_t *tmp;

            if (nodes[i]->letter < nodes[j]->letter) continue;

            tmp = nodes[i];
            nodes[i] = nodes[j];
            nodes[j] = tmp;
        }
        if (node->btree != NULL) {
            free(node->btree);
            node->btree = NULL;
        }
    node->btree = reinterpret_cast<acmp_btree_node_t *>(calloc(1, sizeof(acmp_btree_node_t)));

    /* ENH: Check alloc succeded */
    pos = count / 2;
    node->btree->node = nodes[pos];
    node->btree->letter = nodes[pos]->letter;
    acmp_add_btree_leaves(node->btree, nodes, pos, -1, count);
    for (i = 0; i < count; i++) {
        if (nodes[i]->child != NULL) acmp_build_binary_tree(parser, nodes[i]);
    }
    if (nodes != NULL) {
        free(nodes);
    }
}

/**
 * Constructs fail paths on keyword trie
 */
static int acmp_connect_fail_branches(ACMP *parser) {
    /* Already connected ? */
    acmp_node_t *child, *node, *goto_node;

    if (parser->is_failtree_done != 0) return 1;

    std::vector<acmp_node_t *> arr;
    std::vector<acmp_node_t *> arr2;
    std::vector<acmp_node_t *> tmp;

    parser->root_node->text = (char *)"";

    parser->root_node->fail = parser->root_node;

    /* All first-level children will fail back to root node */
    for (child = parser->root_node->child; child != NULL; child = child->sibling) {
        child->fail = parser->root_node;
        arr.push_back(child);
    }

    for (;;) {
        while (arr.empty() == false) {
            node = arr.back();
            arr.pop_back();
            node->fail = parser->root_node;
            if (node->parent != parser->root_node) {
                goto_node = acmp_child_for_code(node->parent->fail, node->letter);
                node->fail = (goto_node != NULL) ? goto_node : parser->root_node;
            }
#ifdef DEBUG_ACMP
            fprintf(stderr, "fail direction: *%s* => *%s*\n", node->text, node->fail->text);
#endif
            child = node->child;
            while (child != NULL) {
                arr2.push_back(child);
                child = child->sibling;
            }
        }
        if (arr2.empty() == true) break;

        tmp = arr;
        arr = arr2;
        arr2 = tmp;
    }

    acmp_connect_other_matches(parser, parser->root_node);
    if (parser->root_node->child != NULL) acmp_build_binary_tree(parser, parser->root_node);
    parser->is_failtree_done = 1;

    return 1;
}

/*
 *******************************************************************************
 *******************************************************************************
 * Code for functions from header file
 */


/**
 * flags - OR-ed values of ACMP_FLAG constants
 */
ACMP *acmp_create(int flags) {
    ACMP *parser;

    parser = reinterpret_cast<ACMP *>(calloc(1, sizeof(ACMP)));
    /* ENH: Check alloc succeded */
    parser->is_case_sensitive = (flags & ACMP_FLAG_CASE_SENSITIVE) == 0 ? 0 : 1;
    parser->root_node = reinterpret_cast<acmp_node_t *>(calloc(1, sizeof(acmp_node_t)));
    /* ENH: Check alloc succeded */
    return parser;
}

/**
 * Creates fail tree and initializes buffer
 */
int acmp_prepare(ACMP *parser) {
    int st;

    if (parser->bp_buff_len < parser->longest_entry) {
        parser->bp_buff_len = parser->longest_entry * 2;
        //parser->bp_buffer = (size_t *)calloc(1, sizeof(size_t) * parser->bp_buff_len);
        /* ENH: Check alloc succeded */
    }

    st = acmp_connect_fail_branches(parser);
    parser->active_node = parser->root_node;
    if (st != 1) return st;
    parser->is_active = 1;
    return 1;
}

/**
 * Adds pattern to parser
 * parser - ACMP parser
 * pattern - string nwith pattern to match
 * callback - Optional, pointer to an acmp_callback_t function
 * data - pointer to data that will be passed to callback function, only used if callback
 *   is supplied
 * len - Length of pattern in characters, if zero string length is used.
 */
int acmp_add_pattern(ACMP *parser, const char *pattern,
        acmp_callback_t callback, void *data, size_t len)
{
    size_t length, i, j;
    long *ucs_chars;
    acmp_node_t *parent, *child;

if (parser->is_active != 0) return -1;
    length = (len == 0) ? acmp_strlen(parser, pattern) : len;
    ucs_chars = (long *)calloc(1, length * sizeof(long));
    /* ENH: Check alloc succeded */

    parent = parser->root_node;
    acmp_strtoucs(parser, pattern, ucs_chars, length);

    for (i = 0; i < length; i++) {
        long letter = ucs_chars[i];
        if (parser->is_case_sensitive == 0) {
            letter = tolower(letter);
        }
        child = acmp_child_for_code(parent, letter);
        if (child == NULL) {
            child = reinterpret_cast<acmp_node_t *>(calloc(1, sizeof(acmp_node_t)));
            /* ENH: Check alloc succeded */
            child->pattern = (char *)"";
            child->letter = letter;
            child->depth = i;
            child->text = (char *)calloc(1, strlen(pattern) + 2);
            /* ENH: Check alloc succeded */
            for (j = 0; j <= i; j++) child->text[j] = pattern[j];
        }
        if (i == length - 1) {
            if (child->is_last == 0) {
                parser->dict_count++;
                child->is_last = 1;
                child->pattern = (char *)calloc(1, strlen(pattern) + 2);
                /* ENH: Check alloc succeded */
                strcpy(child->pattern, pattern);
            }
            child->callback = callback;
            child->callback_data = data;
        }
        acmp_add_node_to_parent(parent, child);
        parent = child;
    }
    if (length > parser->longest_entry) parser->longest_entry = length;
    parser->is_failtree_done = 0;
    free(ucs_chars);
    return 1;
}

/**
 * Process the data using ACMPT to keep state, and ACMPT's parser to keep the tree
 */
int acmp_process_quick(ACMPT *acmpt, const char **match, const char *data, size_t len) {
    ACMP *parser;
    acmp_node_t *node, *go_to;
    const char *end;
    int offset = 0;

    /*
    if (acmpt->parser->is_failtree_done == 0) {
        acmp_prepare(acmpt->parser);
    };
    */

    parser = acmpt->parser;
    if (acmpt->ptr == NULL) acmpt->ptr = parser->root_node;
    node = reinterpret_cast<acmp_node_t *>(acmpt->ptr);
    end = data + len;

    while (data < end) {
        long letter = (unsigned char)*data++;

        if (parser->is_case_sensitive == 0) letter = tolower(letter);

        go_to = NULL;
        while (go_to == NULL) {
            go_to = acmp_goto(node, letter);
            if (go_to != NULL) {
                if (go_to->is_last) {
                    *match = go_to->text;
                    return offset;
                }
            }
            if (node == parser->root_node) break;
            if (go_to == NULL) node = node->fail;
        }
        if (go_to != NULL) node = go_to;

        /* If node has o_match, then we found a pattern */
        if (node->o_match != NULL) {
            *match = node->text;
            return offset;
        }
        offset++;
    }
    acmpt->ptr = node;
    return -1;
}

}
