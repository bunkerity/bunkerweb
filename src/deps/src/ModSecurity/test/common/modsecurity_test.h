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

#include <iostream>
#include <utility>
#include <string>
#include <vector>
#include <unordered_map>

#ifndef TEST_COMMON_MODSECURITY_TEST_H_
#define TEST_COMMON_MODSECURITY_TEST_H_


extern void print_help();
extern std::string default_test_path;

namespace modsecurity_test {

template <class T> class ModSecurityTest :
    public std::unordered_map<std::string, std::vector<T *> *> {
 public:
    ModSecurityTest()
        : m_test_number(0),
        m_automake_output(false),
        m_count_all(false) { }

    std::string header();
    void cmd_options(int, char **);
    std::pair<std::string, std::vector<T *>>* load_tests();
    std::pair<std::string, std::vector<T *>>* load_tests(std::string path);
    bool load_test_json(std::string);

    std::string target;
    bool verbose = false;
    bool color = false;
    int m_test_number;
    bool m_automake_output;
    bool m_count_all;
};

}  // namespace modsecurity_test

#include "test/common/modsecurity_test.cc"


#endif  // TEST_COMMON_MODSECURITY_TEST_H_
