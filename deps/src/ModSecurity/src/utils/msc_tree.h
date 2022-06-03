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


/*
 *
 * TODO: This is an improved copy of the ModSecurity 2.9 file, this may need
 * some other enhancements and/or fixes.
 *
 */

#ifndef SRC_UTILS_MSC_TREE_H_
#define SRC_UTILS_MSC_TREE_H_


typedef struct CPTData CPTData;
typedef struct TreePrefix TreePrefix;
typedef struct TreeNode TreeNode;
typedef struct CPTTree CPTTree;
typedef struct TreeRoot TreeRoot;

#define IPV4_TREE 0x1
#define IPV6_TREE 0x2

#define IPV4_LEN 0x20
#define IPV6_LEN 0x80

#define TREE_CHECK(x, y) ((x) & (y))
#define MASK_BITS(x) ((x + 1) * 8)
#define SHIFT_LEFT_MASK(x) ((-1) << (x))
#define SHIFT_RIGHT_MASK(x,y) ((x) >> (y))

#define NETMASK_256 0x100
#define NETMASK_128 0x80
#define NETMASK_64  0x40
#define NETMASK_32 0x20
#define NETMASK_16 0x10
#define NETMASK_8  0x8
#define NETMASK_4  0x4
#define NETMASK_2  0x2

#define FALSE 0
#define TRUE 1

extern "C" {

struct CPTData {
    unsigned char netmask;
    struct CPTData *next;
};

struct TreePrefix {
    unsigned char *buffer;
    unsigned int bitlen;
    CPTData *prefix_data;
};

struct TreeNode {
    unsigned int bit;
    int count;
    unsigned char *netmasks;
    TreePrefix *prefix;
    struct TreeNode *left, *right;
    struct TreeNode *parent;
};

struct CPTTree {
    int count;
    TreeNode *head;
};

struct TreeRoot {
    CPTTree *ipv4_tree;
    CPTTree *ipv6_tree;
};

CPTTree *CPTCreateRadixTree();
TreeNode *CPTIpMatch(unsigned char *ipdata, CPTTree *tree, int type);
TreeNode *TreeAddIP(const char *buffer, CPTTree *tree, int type);

unsigned char is_netmask_v4(char *ip_strv4);

unsigned char is_netmask_v6(char *ip_strv6);

/** @ingroup ModSecurity_Legacy */
int tree_contains_ip(TreeRoot *rtree,
    const char *value, char **error_msg);

int add_ip_from_param(const char *param, TreeRoot **rtree, char **error_msg);
int ip_tree_from_param(const char *param, TreeRoot **rtree, char **error_msg);
int create_radix_tree(TreeRoot **rtree, char **error_msg);
}

#endif  // SRC_UTILS_MSC_TREE_H_
