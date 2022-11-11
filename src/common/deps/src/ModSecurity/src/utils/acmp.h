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

#ifndef ACMP_H_
#define ACMP_H_

#define ACMP_FLAG_BYTE               0
#define ACMP_FLAG_CASE_SENSITIVE     1
#define ACMP_FLAG_CASE_INSENSITIVE   0
#ifdef ACMP_USE_UTF8
#define ACMP_FLAG_UTF8               0x100
#endif

#include <cstddef>


extern "C" {
/**
 * Opaque struct with parser data
 */
typedef struct ACMP ACMP;

/**
 * Used to separate state from the trie for acmp_process_quick function
 */
typedef struct {
    ACMP *parser;
    void *ptr;
} ACMPT;

/*
 *******************************************************************************
 *******************************************************************************
 * Data structures for acmp parser
 */

/**
 * Callback function. Arguments are:
 * ACMP * - acmp parser that initiated callback
 * void * - custom data you supplied when adding callback
 * size_t - position in bytes where pattern was found
 * size_t - position in chars where pattern was found, for multibyte strings
 */
typedef void (*acmp_callback_t)(ACMP *, void *, size_t, size_t);


/**
 * One node in trie
 */
typedef struct acmp_node_t acmp_node_t;
typedef struct acmp_btree_node_t acmp_btree_node_t;
struct acmp_node_t {
    long letter;
    int  is_last;
    acmp_callback_t callback;
    void *callback_data;
    int depth;

    acmp_node_t *child;
    acmp_node_t *sibling;
    acmp_node_t *fail;
    acmp_node_t *parent;
    acmp_node_t *o_match;

    acmp_btree_node_t *btree;

    size_t hit_count;

    char *text;
    char *pattern;
};

struct acmp_btree_node_t {
    long letter;
    acmp_btree_node_t *left;
    acmp_btree_node_t *right;
    acmp_node_t *node;
};

/**
 * Data related to parser, not to individual nodes
 */
struct ACMP {

    int is_case_sensitive;

    int dict_count;
    size_t longest_entry;

    acmp_node_t *root_node;

    const char *data_start;
    const char *data_end;
    const char *data_pos;
    size_t data_len;

    size_t *bp_buffer;
    size_t bp_buff_len;

    acmp_node_t *active_node;
    char u8_buff[6];
    size_t  u8buff_len;
    size_t  hit_count;
    int  is_failtree_done;
    int  is_active;
    size_t  byte_pos;
    size_t  char_pos;
};


//static long utf8_lcase(long ucs_code);

/**
 * flags - OR-ed values of ACMP_FLAG constants
 */
ACMP *acmp_create(int flags);

/**
 * Destroys previously created parser
 */
void acmp_destroy(ACMP *parser);

/**
 * Creates parser with same options and same patterns
 * parser - ACMP parser to duplicate
 */
ACMP *acmp_duplicate(ACMP *parser);

/**
 * Adds pattern to parser. Cannot be done after starting the search.
 * parser - ACMP parser
 * pattern - string with pattern to match
 * callback - Optional, pointer to an acmp_callback_t function
 * data - pointer to data that will be passed to callback function, only used if callback
 *   is supplied
 * len - Length of pattern in characters, if zero string length is used.
 */
int acmp_add_pattern(ACMP *parser, const char *pattern,
    acmp_callback_t callback, void *data, size_t len);

/**
 * Called to process incoming data stream. You must call acmp_done after sending
 *   last data packet
 *
 * data - ptr to incoming data
 * len  - size of data in bytes
 */
int acmp_process(ACMP *parser, const char *data, size_t len);

/**
 * Returns number of matches on all patterns combined
 */
size_t acmp_match_count_total(ACMP *parser);

/**
 * Returns number of matches for given pattern
 */
size_t acmp_match_count(ACMP *parser, const char *pattern);

/**
 * Resets the state of parser so you can start using it with new set of data,
 * or add new patterns.
 */
void acmp_reset(ACMP *parser);

/**
 * Creates an ACMPT struct that will use parser's tree, without duplicating its data
 */
ACMPT *acmp_duplicate_quick(ACMP *parser);

/**
 * Process the data using ACMPT to keep state, and ACMPT's parser to keep the tree
 */
int acmp_process_quick(ACMPT *acmpt, const char **match, const char *data, size_t len);

/**
 * Prepares parser for searching
 */
int acmp_prepare(ACMP *parser);

char *parse_pm_content(const char *op_parm, unsigned short int op_len, const char **error_msg);

}

#endif /*ACMP_H_*/
