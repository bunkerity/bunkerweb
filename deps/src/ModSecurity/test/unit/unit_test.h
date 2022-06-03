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

#include <yajl/yajl_tree.h>

#include <iostream>
#include <unordered_map>
#include <vector>
#include <string>

#ifndef TEST_UNIT_UNIT_TEST_H_
#define TEST_UNIT_UNIT_TEST_H_

namespace modsecurity_test {

class UnitTest {
 public:
    static UnitTest *from_yajl_node(yajl_val &);

    std::string print();

    std::string param;
    std::string input;
    std::string resource;
    std::string name;
    std::string type;
    std::string filename;
    std::string output;
    int ret;
    int obtained;
    int skipped;
    std::string obtainedOutput;
};

}  // namespace modsecurity_test

#endif  // TEST_UNIT_UNIT_TEST_H_
