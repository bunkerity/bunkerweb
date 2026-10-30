/*
 * ModSecurity for Apache 2.x, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef WIN32
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#else
#include "src/compat/msvc.h"
#include <WinSock2.h>
#include <WS2tcpip.h>
#endif

#include "src/utils/msc_tree.h"

extern "C" {

CPTTree *CPTCreateRadixTree()   {
    CPTTree *tree;

    tree = reinterpret_cast<CPTTree *>(malloc(sizeof(CPTTree)));

    if(tree == NULL)
        return NULL;

    memset(tree, 0, sizeof(CPTTree));

    return tree;
}

void ConvertIPNetmask(unsigned char *buffer, unsigned char netmask, unsigned int ip_bitmask) {
    int aux = 0, bytes = 0;
    int mask = 0;

    bytes = ip_bitmask/8;

    while(aux < bytes)    {
        int mask_bit  = ((1+aux) * 8);

        if (mask_bit > netmask) {
            mask = 0;
            if ((mask_bit - netmask) < 8)   mask = SHIFT_LEFT_MASK(mask_bit - netmask);
        }   else    {
            mask = -1;
        }

        buffer[aux] &= mask;
        aux++;
    }

    return;
}

TreeNode *CPTCreateNode()   {
    TreeNode *node;

    node = reinterpret_cast<TreeNode *>(malloc(sizeof(TreeNode)));

    if(node == NULL)
        return NULL;

    memset(node, 0, sizeof(TreeNode));
    return node;
}

CPTData *CPTCreateCPTData(unsigned char netmask) {

    CPTData *prefix_data = reinterpret_cast<CPTData *>(malloc(sizeof(CPTData)));

    if (prefix_data == NULL) {
        return NULL;
    }

    memset(prefix_data, 0, sizeof(CPTData));

    prefix_data->netmask = netmask;

    return prefix_data;
}

TreePrefix *InsertDataPrefix(TreePrefix *prefix, unsigned char *ipdata, unsigned int ip_bitmask,
        unsigned char netmask)  {

    if(prefix == NULL)
        return NULL;

    memcpy(prefix->buffer, ipdata, ip_bitmask/8);
    prefix->bitlen = ip_bitmask;

    prefix->prefix_data = CPTCreateCPTData(netmask);

    if(prefix->prefix_data == NULL)
        return NULL;

    return prefix;
}

TreePrefix *CPTCreatePrefix(unsigned char *ipdata, unsigned int ip_bitmask,
        unsigned char netmask)  {

    TreePrefix *prefix = NULL;
    int bytes = ip_bitmask;

    if ((ip_bitmask % 8 != 0) || (ipdata == NULL)) {
        return NULL;
    }

    prefix = reinterpret_cast<TreePrefix *>(malloc(sizeof(TreePrefix)));
    if (prefix == NULL)
        return NULL;

    memset(prefix, 0, sizeof(TreePrefix));

    prefix->buffer = reinterpret_cast<unsigned char *>(malloc(bytes));

    if (prefix->buffer == NULL) {
        free(prefix);
        return NULL;
    }

    memset(prefix->buffer, 0, bytes);

    return InsertDataPrefix(prefix, ipdata, ip_bitmask, netmask);
}

void CPTAppendToCPTDataList(CPTData *n, CPTData **list)  {
    CPTData *temp = NULL, *prev = NULL;

    if (n == NULL) {
        return;
    }

    if (list == NULL) {
        return;
    }

    prev = *list;
    temp = *list;

    while (temp != NULL) {
        if (n->netmask > temp->netmask)
            break;
        prev = temp;
        temp = temp->next;
    }

    if (temp == *list) {
        n->next = *list;
        *list = n;
    } else {
        n->next = prev->next;
        prev->next = n;
    }

    return;
}

int TreePrefixContainNetmask(TreePrefix *prefix, unsigned char netmask)   {
    CPTData *prefix_data = NULL;

    if (prefix == NULL) {
        return 0;
    }

    prefix_data = prefix->prefix_data;

    while (prefix_data != NULL) {
        if (prefix_data->netmask == netmask)
            return 1;
        prefix_data = prefix_data->next;
    }

    return 0;
}

int CheckBitmask(unsigned char netmask, unsigned int ip_bitmask)   {

    switch(netmask) {

        case 0xff:
            return 1;
        case 0x20:
            if(ip_bitmask == 0x20)
                return 1;
            break;
        case 0x80:
            if(ip_bitmask == 0x80)
                return 1;
            break;
    }

    return 0;
}

TreeNode *CPTCreateHead(TreePrefix *prefix, TreeNode *node, CPTTree *tree, unsigned char netmask, unsigned int ip_bitmask)    {

    if(tree == NULL)
        return NULL;

    if(prefix == NULL)
        return NULL;

    if (node != NULL)   {

        node->prefix = prefix;
        node->bit = prefix->bitlen;
        tree->head = node;

        if(CheckBitmask(netmask, ip_bitmask))
            return node;

        node->count++;
        node->netmasks = reinterpret_cast<unsigned char *>(malloc(node->count *  sizeof(unsigned char)));

        if(node->netmasks)
            node->netmasks[0] = netmask;

        return node;

    } else {
        return NULL;
    }

    return NULL;
}

TreeNode *SetParentNode(TreeNode *node, TreeNode *new_node, CPTTree *tree)  {

    if (node->parent == NULL)
        tree->head = new_node;
    else if (node->parent->right == node)
        node->parent->right = new_node;
    else
        node->parent->left = new_node;

    return new_node;
}

int InsertNetmask(TreeNode *node, TreeNode *parent, TreeNode *new_node,
        CPTTree *tree, unsigned char netmask, unsigned char bitlen) {
    if (netmask != NETMASK_256-1 && netmask != NETMASK_128) {
        if (netmask != NETMASK_32 || bitlen != NETMASK_32) {
            int i;
            node = new_node;
            parent = new_node->parent;

            while (parent != NULL && netmask < (parent->bit + 1)) {
                node = parent;
                parent = parent->parent;
            }

            node->count++;

            node->netmasks = reinterpret_cast<unsigned char *>(malloc(node->count * sizeof(unsigned char)));
            if(node->netmasks == NULL) {
                return 0;
            }
            memset(node->netmasks, 0, (node->count *  sizeof(unsigned char)));

            if ((node->count-1) == 0) {
                node->netmasks[0] = netmask;
                return 1;
            }

            node->netmasks[node->count - 1] = netmask;

            i = node->count - 2;
            while (i >= 0) {
                if (netmask < node->netmasks[i]) {
                    node->netmasks[i + 1] = netmask;
                    break;
                }

                node->netmasks[i + 1] = node->netmasks[i];
                node->netmasks[i] = netmask;
                i--;
            }
        }
    }

    return 0;
}

TreeNode *CPTAddElement(unsigned char *ipdata, unsigned int ip_bitmask, CPTTree *tree, unsigned char netmask)   {
    unsigned char *buffer = NULL;
    unsigned char bitlen = 0;
    int bit_validation = 0, test_bit = 0;
    size_t i = 0;
    unsigned int x, y;
    TreeNode *node = NULL, *new_node = NULL;
    TreeNode *parent = NULL, *i_node = NULL;
    TreeNode *bottom_node = NULL;
    TreePrefix *prefix = NULL;

    if (tree == NULL) {
        return NULL;
    }

    ConvertIPNetmask(ipdata, netmask, ip_bitmask);

    prefix = CPTCreatePrefix(ipdata, ip_bitmask, netmask);

    if (prefix == NULL) {
        return NULL;
    }

    if (tree->head == NULL) {
        node = CPTCreateNode();
        return CPTCreateHead(prefix, node, tree, netmask, ip_bitmask);
    }

    node = tree->head;
    buffer = prefix->buffer;
    bitlen = prefix->bitlen;

    while (node->bit < bitlen || node->prefix == NULL) {

        if (bitlen < node->bit) {
            if (node->right == NULL)
                break;
            else
                node = node->right;
        } else {
            x = SHIFT_RIGHT_MASK(node->bit, 3); y = SHIFT_RIGHT_MASK(NETMASK_128, (node->bit % 8));

            if (TREE_CHECK(buffer[x],y)) {
                if (node->right == NULL)
                    break;
                node = node->right;
            } else {
                if (node->left == NULL)
                    break;
                else
                    node = node->left;
            }
        }
    }

    bottom_node = node;

    if(node->bit < bitlen)
        bit_validation = node->bit;
    else
        bit_validation = bitlen;

    for (i = 0; (i * NETMASK_8) < bit_validation; i++) {
        int net = 0, div = 0;
        int cnt = 0;
        int temp;

        if ((temp = (buffer[i] ^ bottom_node->prefix->buffer[i])) == 0) {
            test_bit = (i + 1) * NETMASK_8;
            continue;
        }

        temp += temp;

        for(cnt = 0, net = NETMASK_256, div = 2; net >= NETMASK_2; net = NETMASK_256/div,
                div += div, cnt++)      {
            if(temp >= net)   {
                test_bit = (i * NETMASK_8) + cnt;
                break;
            }
        }
        break;
    }

    if (bit_validation < test_bit)
        test_bit = bit_validation;

    parent = node->parent;

    while (parent && test_bit <= parent->bit) {
        node = parent;
        parent = node->parent;
    }

    if (test_bit == bitlen && node->bit == bitlen) {
        if (node->prefix != NULL) {
            int found = 0;
            CPTData *prefix_data;

            prefix_data = node->prefix->prefix_data;

            while(prefix_data != NULL)  {
                if (prefix_data->netmask == netmask)
                    ++found;
                prefix_data = prefix_data->next;
            }

            if (found != 0) {

                CPTData *prefix_data = CPTCreateCPTData(netmask);
                CPTAppendToCPTDataList(prefix_data, &prefix->prefix_data);

                if(CheckBitmask(netmask, ip_bitmask))
                    return node;

                parent = node->parent;
                while (parent != NULL && netmask < (parent->bit + 1)) {
                    node = parent;
                    parent = parent->parent;
                }

                node->count++;
                new_node = node;
                node->netmasks = reinterpret_cast<unsigned char *>(malloc(node->count *  sizeof(unsigned char)));
                memset(node->netmasks, 0, (node->count *  sizeof(unsigned char)));

                if ((node->count -1) == 0) {
                    node->netmasks[0] = netmask;
                    return new_node;
                }

                node->netmasks[node->count - 1] = netmask;

                int index = node->count - 2;
                while (index >= 0) {
                    if (netmask < node->netmasks[index]) {
                        node->netmasks[index + 1] = netmask;
                        break;
                    }

                    node->netmasks[index + 1] = node->netmasks[index];
                    node->netmasks[index] = netmask;
                    index--;
                }
            }
        } else {
            node->prefix = CPTCreatePrefix(prefix->buffer, prefix->bitlen,
                    NETMASK_256-1);
        }
        return node;
    }

    new_node = CPTCreateNode();

    if(new_node == NULL)
        return NULL;

    new_node->prefix = prefix;
    new_node->bit = prefix->bitlen;

    if (test_bit == bitlen) {

        x = SHIFT_RIGHT_MASK(test_bit, 3); y = SHIFT_RIGHT_MASK(NETMASK_128, (test_bit % 8));

        if (TREE_CHECK(bottom_node->prefix->buffer[x],y)) {
            new_node->right = node;
        } else {
            new_node->left = node;
        }

        new_node->parent = node->parent;
        node->parent = SetParentNode(node, new_node, tree);

    } else {
        i_node = CPTCreateNode();

        if (i_node == NULL) {
            free(new_node->prefix);
            free(new_node);
            return NULL;
        }

        //i_node->prefix = NULL;
        i_node->bit = test_bit;
        i_node->parent = node->parent;

        if (node->netmasks != NULL) {
            i = 0;
            int j;
            while(i < node->count) {
                if (node->netmasks[i] < test_bit + 1)
                    break;
                i++;
            }

            i_node->netmasks = reinterpret_cast<unsigned char *>(malloc((node->count - i) * sizeof(unsigned char)));
            memset(i_node->netmasks, 0, ((node->count - i) * sizeof(unsigned char)));

            if(i_node->netmasks == NULL) {
                free(new_node->prefix);
                free(new_node);
                free(i_node);
                return NULL;
            }

            j = 0;
            while (j < (node->count - i))   {
                i_node->netmasks[j] = node->netmasks[i + j];
                j++;
            }

            i_node->count = (node->count - i);
            node->count = i;

            if (node->count == 0) {
                node->netmasks = NULL;
            }
        }

        x = SHIFT_RIGHT_MASK(test_bit, 3); y = SHIFT_RIGHT_MASK(NETMASK_128, (test_bit % 8));

        if (TREE_CHECK(buffer[x],y)) {
            i_node->left = node;
            i_node->right = new_node;
        } else {
            i_node->left = new_node;
            i_node->right = node;
        }

        new_node->parent = i_node;
        node->parent = SetParentNode(node, i_node, tree);
    }

    if (InsertNetmask(node, parent, new_node, tree, netmask, bitlen))
        return new_node;

    return new_node;
}

int TreeCheckData(TreePrefix *prefix, CPTData *prefix_data, unsigned int netmask)   {

    while(prefix_data != NULL)  {
        if (prefix_data->netmask == netmask) {
            return 1;
        }
        prefix_data = prefix_data->next;
    }

    return 0;
}

int TreePrefixNetmask(TreePrefix *prefix, unsigned int netmask, int flag)   {
    CPTData *prefix_data = NULL;
    int ret = 0;

    if (prefix == NULL) {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "TreePrefixNetmask: prefix is NULL.");
        //}
        return 0;
    }

    prefix_data = prefix->prefix_data;

    if (flag == 1) {

        if(prefix_data == NULL) return 0;

        if (prefix_data->netmask != netmask) {
            //if (msr && msr->txcfg->debuglog_level >= 9) {
            //    msr_log(msr, 9, "TreePrefixNetmask: Cannot find a prefix with correct netmask.");
            //}
            return 0;
        } else {
            //if (msr && msr->txcfg->debuglog_level >= 9) {
            //    msr_log(msr, 9, "TreePrefixNetmask: Found a prefix with correct netmask.");
            //}
            return 1;
        }
    }

    //if (msr && msr->txcfg->debuglog_level >= 9) {
    //    msr_log(msr, 9, "TreePrefixNetmask: Check if a prefix has a the correct netmask");
    //}

    ret = TreeCheckData(prefix, prefix_data, netmask);

    return ret;
}

TreeNode *CPTRetriveNode(unsigned char *buffer, unsigned int ip_bitmask, TreeNode *node)  {

    if(node == NULL)    {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTRetriveNode: Node tree is NULL.");
        //}
        return NULL;
    }

    if(buffer == NULL)  {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTRetriveNode: Empty ip address. Nothing to search for.");
        //}
        return NULL;
    }

    while (node->bit < ip_bitmask) {
        unsigned int x = SHIFT_RIGHT_MASK(node->bit, 3);
        unsigned int y = SHIFT_RIGHT_MASK(NETMASK_128, (node->bit % 8));

        if (TREE_CHECK(buffer[x], y)) {
            node = node->right;
            if (node == NULL)   return NULL;
        } else {
            node = node->left;
            if (node == NULL)   return NULL;
        }
    }

    //if (msr && msr->txcfg->debuglog_level >= 9) {
    //    msr_log(msr, 9, "CPTRetriveNode: Found the node for provided ip address.");
    //}


    return node;
}

TreeNode *CPTRetriveParentNode(TreeNode *node)  {

    while (node != NULL && node->netmasks == NULL)
        node = node->parent;

    return node;
}

TreeNode *CPTFindElementIPNetblock(unsigned char *ipdata, unsigned char ip_bitmask, TreeNode *node) {
    TreeNode *netmask_node = NULL;
    int mask = 0;
    int i = 0, j = 0;
    int mask_bits = 0;

    node = CPTRetriveParentNode(node);

    if (node == NULL)   {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElementIPNetblock: Node tree is NULL.");
        //}
        return NULL;
    }

    netmask_node = node;

    while(j < netmask_node->count)    {
        int bytes = ip_bitmask / 8;

        while( i < bytes )  {

            mask = -1;
            mask_bits = ((i + 1) * 8);

            if (mask_bits > netmask_node->netmasks[j]) {
                if ((mask_bits - netmask_node->netmasks[j]) < 8)
                    mask = SHIFT_LEFT_MASK(mask_bits - netmask_node->netmasks[j]);
                else
                    mask = 0;
            }

            ipdata[i] &= mask;
            i++;
        }

        node = CPTRetriveNode(ipdata, ip_bitmask, node);

        if(node == NULL)    {
            //if (msr && msr->txcfg->debuglog_level >= 9) {
            //    msr_log(msr, 9, "CPTFindElement: Node tree is NULL.");
            //}
            return node;
        }

        if (node->bit != ip_bitmask)    {
            //if (msr && msr->txcfg->debuglog_level >= 9) {
            //    msr_log(msr, 9, "CPTFindElementIPNetblock: Found a tree node but netmask is different.");
            //}
            return NULL;
        }

        if (node->prefix == NULL)   {
            //if (msr && msr->txcfg->debuglog_level >= 9) {
            //    msr_log(msr, 9, "CPTFindElementIPNetblock: Found a tree node but prefix is NULL.");
            //}
            return NULL;
        }

        if (memcmp(node->prefix->buffer, ipdata, bytes) == 0) {
            mask = SHIFT_LEFT_MASK(8 - ip_bitmask % 8);

            if ((ip_bitmask % 8) == 0) {
                if (TreePrefixNetmask(node->prefix, netmask_node->netmasks[j], FALSE)) {
                    //if (msr && msr->txcfg->debuglog_level >= 9) {
                    //    msr_log(msr, 9, "CPTFindElementIPNetblock: Node found for provided ip address");
                    //}
                    return node;
                }
            }

            if ((node->prefix->buffer[bytes] & mask) == (ipdata[bytes] & mask)) {
                if (TreePrefixNetmask(node->prefix, netmask_node->netmasks[j], FALSE)) {
                    //if (msr && msr->txcfg->debuglog_level >= 9) {
                    //    msr_log(msr, 9, "CPTFindElementIPNetblock: Node found for provided ip address");
                    //}
                    return node;
                }
            }
        }

        j++;
    }

    return CPTFindElementIPNetblock(ipdata, ip_bitmask, netmask_node->parent);
}

TreeNode *CPTFindElement(unsigned char *ipdata, unsigned int ip_bitmask, CPTTree *tree)   {
    TreeNode *node = NULL;
    int mask = 0, bytes = 0;
    unsigned char temp_data[NETMASK_256-1];

    if (tree == NULL)   {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Tree is NULL. Cannot proceed searching the ip.");
        //}
        return node;
    }

    if (tree->head == NULL) {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Tree head is NULL. Cannot proceed searching the ip.");
        //}
        return node;
    }

    node = tree->head;

    if (ip_bitmask > (NETMASK_256-1))   {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Netmask cannot be greater than 255");
        //}
        return NULL;
    }

    bytes = ip_bitmask/8;

    memset(temp_data, 0, NETMASK_256-1);
    memcpy(temp_data, ipdata, bytes);

    node = CPTRetriveNode(temp_data, ip_bitmask, node);

    if(node == NULL)    {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Node tree is NULL.");
        //}
        return node;
    }

    if (node->bit != ip_bitmask) {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Found a tree node but netmask is different.");
        //}
        return NULL;
    }

    if(node->prefix == NULL)    {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
        //    msr_log(msr, 9, "CPTFindElement: Found a tree node but prefix is NULL.");
        //}
        return node;
    }

    if ((node->netmasks == NULL) && memcmp(node->prefix->buffer, temp_data, bytes) == 0) {
        mask = SHIFT_LEFT_MASK(8 - ip_bitmask % 8);

        if ((ip_bitmask % 8) == 0) {
            if (TreePrefixNetmask(node->prefix, ip_bitmask, TRUE)) {
                //if (msr && msr->txcfg->debuglog_level >= 9) {
                    //msr_log(msr, 9, "CPTFindElement: Node found for provided ip address");
                //}
                return node;
            }
        }
        if ((node->prefix->buffer[bytes] & mask) == (temp_data[bytes] & mask)) {
            if (TreePrefixNetmask(node->prefix, ip_bitmask, TRUE)) {
                //if (msr && msr->txcfg->debuglog_level >= 9) {
                    //msr_log(msr, 9, "CPTFindElement: Node found for provided ip address");
                //}
                return node;
            }
        }
    }

    return CPTFindElementIPNetblock(temp_data, ip_bitmask, node);
}

TreeNode *CPTIpMatch(unsigned char *ipdata, CPTTree *tree, int type)   {

    if(tree == NULL)  {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
            //msr_log(msr, 9, "CPTIpMatch: Tree is NULL. Cannot proceed searching the ip.");
        //}
        return NULL;
    }

    if(ipdata == NULL)  {
        //if (msr && msr->txcfg->debuglog_level >= 9) {
            //msr_log(msr, 9, "CPTIpMatch: Empty ip address. Nothing to search for.");
        //}
        return NULL;
    }

    switch(type)    {
        case IPV4_TREE:
            //if (msr && msr->txcfg->debuglog_level >= 9) {
                //msr_log(msr, 9, "CPTIpMatch: Searching ip type 0x%x", type);
            //}
            return CPTFindElement(ipdata, NETMASK_32, tree);
        case IPV6_TREE:
            //if (msr && msr->txcfg->debuglog_level >= 9) {
                //msr_log(msr, 9, "CPTIpMatch: Searching ip type 0x%x", type);
            //}
            return CPTFindElement(ipdata, NETMASK_128, tree);
        default:
            //if (msr && msr->txcfg->debuglog_level >= 9) {
                //msr_log(msr, 9, "CPTIpMatch: Unknown ip type 0x%x", type);
            //}
            return NULL;
    }
}

TreeNode *TreeAddIP(const char *buffer, CPTTree *tree, int type) {
    unsigned long ip;
    int ret;
    unsigned char netmask_v4 = NETMASK_32, netmask_v6 = NETMASK_128;
    char ip_strv4[NETMASK_32], ip_strv6[NETMASK_128];
    struct in_addr addr4;
    struct in6_addr addr6;
    int pos = 0;
    char *ptr = NULL;

    if(tree == NULL)
        return NULL;

    pos = strchr(buffer, '/') - buffer;

    switch(type)    {

        case IPV4_TREE:
            memset(&(addr4.s_addr), 0, sizeof(addr4.s_addr));
            memset(ip_strv4, 0x0, NETMASK_32);

            strncpy(ip_strv4, buffer, sizeof(ip_strv4));
            *(ip_strv4 + (sizeof(ip_strv4) - 1)) = '\0';

            ptr = strdup(ip_strv4);
            netmask_v4 = is_netmask_v4(ptr);

            if (netmask_v4 > NETMASK_32) {
                free(ptr);
                ptr = NULL;
                return NULL;
            }
            if (ptr != NULL) {
                free(ptr);
                ptr = NULL;
            }
            if (netmask_v4 == 0) {
                return NULL;
            }
            else if (pos < strlen(ip_strv4)) {
                ip_strv4[pos] = '\0';
            }

            ret = inet_pton(AF_INET, ip_strv4, &(addr4.s_addr));

            if (ret <= 0) {
                return NULL;
            }

            tree->count++;
            return CPTAddElement((unsigned char *)&(addr4.s_addr), NETMASK_32, tree, netmask_v4);

        case IPV6_TREE:
            memset(&(addr6.s6_addr), 0, sizeof(addr6.s6_addr));
            memset(ip_strv6, 0x0, NETMASK_128);

            strncpy(ip_strv6, buffer, sizeof(ip_strv6));
            *(ip_strv6 + sizeof(ip_strv6) - 1) = '\0';

            ptr = strdup(ip_strv6);
            netmask_v6 = is_netmask_v6(ptr);

            if (netmask_v6 > NETMASK_128) {
                free(ptr);
                ptr = NULL;
                return NULL;
            }

            if(ptr != NULL) {
                free(ptr);
                ptr = NULL;
            }

            if(netmask_v6 == 0) {
                return NULL;
            }
            else if (netmask_v6 != NETMASK_128 && pos < strlen(ip_strv6)) {
                ip_strv6[pos] = '\0';
            }

            ret = inet_pton(AF_INET6, ip_strv6, &(addr6.s6_addr));

            if (ret <= 0)
            {
                return NULL;
            }

            tree->count++;

            return CPTAddElement((unsigned char *)&(addr6.s6_addr), NETMASK_128, tree, netmask_v6);
        default:
            return NULL;
    }

    return NULL;
}










int tree_contains_ip(TreeRoot *rtree,
    const char *value, char **error_msg)
{
    struct in_addr in;
    struct in6_addr in6;

    if (rtree == NULL)
    {
        return 0;
    }

    if (strchr(value, ':') == NULL) {
        if (inet_pton(AF_INET, value, &(in.s_addr)) <= 0) {
            //*error_msg = apr_psprintf(mp, "IPmatch: bad IPv4 " \
            //    "specification \"%s\".", value);
            return -1;
        }

        if (CPTIpMatch((unsigned char *)&(in.s_addr), rtree->ipv4_tree,
            IPV4_TREE) != NULL) {
            return 1;
        }
    }
    else {
        if (inet_pton(AF_INET6, value, &(in6.s6_addr)) <= 0) {
            //*error_msg = apr_psprintf(mp, "IPmatch: bad IPv6 " \
             //   "specification \"%s\".", value);
            return -1;
        }

        if (CPTIpMatch((unsigned char *)&(in6.s6_addr), rtree->ipv6_tree,
            IPV6_TREE) != NULL) {
            return 1;
        }
    }


    return 0;
}



int add_ip_from_param(
    const char *param, TreeRoot **rtree, char **error_msg)
{
    char *param_copy = strdup(param);
    char *saved = NULL;
    char *str;
    TreeNode *tnode = NULL;

    str = strtok_r(param_copy, ",", &saved);
    while (str != NULL)
    {
        if (strchr(str, ':') == NULL)
        {
            tnode = TreeAddIP(str, (*rtree)->ipv4_tree, IPV4_TREE);
        }
        else
        {
            tnode = TreeAddIP(str, (*rtree)->ipv6_tree, IPV6_TREE);
        }

        if (tnode == NULL)
        {
            //*error_msg = apr_psprintf("Could not add entry " \
            //    "\"%s\" from: %s.", str, param);
            free(param_copy);
            return -1;
        }

        str = strtok_r(NULL, ",", &saved);
    }
    free(param_copy);

    return 0;
}


int ip_tree_from_param(
    const char *param, TreeRoot **rtree, char **error_msg)
{
    char *param_copy = strdup(param);
    char *saved = NULL;
    char *str = NULL;
    TreeNode *tnode = NULL;

    if (create_radix_tree(rtree, error_msg))
    {
        free(param_copy);
        return -1;
    }

    str = strtok_r(param_copy, ",", &saved);
    while (str != NULL)
    {
        if (strchr(str, ':') == NULL)
        {
            tnode = TreeAddIP(str, (*rtree)->ipv4_tree, IPV4_TREE);
        }
        else
        {
            tnode = TreeAddIP(str, (*rtree)->ipv6_tree, IPV6_TREE);
        }

        if (tnode == NULL)
        {
            //*error_msg = apr_psprintf("Could not add entry " \
            //    "\"%s\" from: %s.", str, param);
            free(param_copy);
            return -1;
        }

        str = strtok_r(NULL, ",", &saved);
    }
    free(param_copy);

    return 0;
}


/** \brief Validate IPv4 Netmask
 *
 * \param ip_strv6 Pointer to ipv6 address
 *
 * \retval netmask_v4 On Success
 */
unsigned char is_netmask_v4(char *ip_strv4) {
    unsigned char netmask_v4 = 32;
    char *mask_str = NULL;

    if(ip_strv4 == NULL)
        return netmask_v4;

    if ((mask_str = strchr(ip_strv4, '/'))) {
        int cidr;
        *(mask_str++) = '\0';

        if (strchr(mask_str, '.') != NULL) {
            return 0;
        }

        cidr = atoi(mask_str);
        if (cidr == 32) {
            return 32;
        }
        if ((cidr < 0) || (cidr > 32)) {
            return 0;
        }

        netmask_v4 = (unsigned char)cidr;
    }

    return netmask_v4;
}

/** \brief Validate IPv6 Netmask
 *
 * \param ip_strv6 Pointer to ipv6 address
 *
 * \retval netmask_v6 On Success
 */
unsigned char is_netmask_v6(char *ip_strv6) {
    unsigned char netmask_v6 = 128;
    char *mask_str = NULL;

    if(ip_strv6 == NULL)
        return netmask_v6;

    if ((mask_str = strchr(ip_strv6, '/'))) {
        int cidr;
        *(mask_str++) = '\0';

        if (strchr(mask_str, ':') != NULL) {
            return 0;
        }

        cidr = atoi(mask_str);
        if ((cidr < 0) || (cidr > 128)) {
            return 0;
        }
        netmask_v6 = (unsigned char)cidr;
    }

    return netmask_v6;
}


int create_radix_tree(TreeRoot **rtree, char **error_msg)
{
    *rtree = reinterpret_cast<TreeRoot *>(malloc(sizeof(TreeRoot)));
    if (*rtree == NULL)
    {
        //*error_msg = apr_psprintf(mp, "Failed allocating " \
        //    "memory to TreeRoot.");
        goto root_node_failed;
    }
    memset(*rtree, 0, sizeof(TreeRoot));

    (*rtree)->ipv4_tree = CPTCreateRadixTree();
    if ((*rtree)->ipv4_tree == NULL)
    {
        //*error_msg = apr_psprintf(mp, "IPmatch: Tree initialization " \
        //    "failed.");
        goto ipv4_tree_failed;
    }

    (*rtree)->ipv6_tree = CPTCreateRadixTree();
    if ((*rtree)->ipv6_tree == NULL)
    {
        //*error_msg = apr_psprintf(mp, "IPmatch: Tree initialization " \
        //    "failed.");
        goto ipv6_tree_failed;
    }

    return 0;

ipv6_tree_failed:
ipv4_tree_failed:
root_node_failed:
    return -1;
}

}
