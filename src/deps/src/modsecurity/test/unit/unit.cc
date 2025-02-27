/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <string.h>
#include <cstring>
#include <cassert>
#include <thread>
#include <array>
#include <iostream>
#include <ctime>
#include <string>

#include "modsecurity/rules_set.h"
#include "modsecurity/modsecurity.h"
#include "src/operators/operator.h"
#include "src/actions/transformations/transformation.h"
#include "modsecurity/transaction.h"
#include "modsecurity/actions/action.h"


#include "test/common/modsecurity_test.h"
#include "test/common/modsecurity_test_results.h"
#include "test/common/modsecurity_test_context.h"
#include "test/common/colors.h"
#include "test/unit/unit_test.h"
#include "src/utils/string.h"




using modsecurity_test::UnitTest;
using modsecurity_test::UnitTestResult;
using modsecurity_test::ModSecurityTest;
using modsecurity_test::ModSecurityTestResults;
using modsecurity::actions::transformations::Transformation;
using modsecurity::operators::Operator;

std::string default_test_path = "test-cases/secrules-language-tests/operators";
static std::list<std::string> resources;

void print_help() {
    std::cout << "Use ./unit /path/to/file" << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;
}


struct OperatorTest {
    using ItemType = Operator;

    static ItemType* init(const UnitTest &t) {
        auto op = Operator::instantiate(t.name, t.param);
        assert(op != nullptr);

        std::string error;
        op->init(t.filename, &error);

        return op;
    }

    static UnitTestResult eval(ItemType &op, const UnitTest &t, modsecurity::Transaction &transaction) {
        modsecurity::RuleWithActions rule{nullptr, nullptr, "dummy.conf", -1};
        modsecurity::RuleMessage ruleMessage{rule, transaction};
        return {op.evaluate(&transaction, &rule, t.input, ruleMessage), {}};
    }

    static bool check(const UnitTestResult &result, const UnitTest &t) {
        return result.ret != t.ret;
    }
};


struct TransformationTest {
    using ItemType = Transformation;

    static ItemType* init(const UnitTest &t) {
        auto tfn = Transformation::instantiate("t:" + t.name);
        assert(tfn != nullptr);

        return tfn;
    }

    static UnitTestResult eval(const ItemType &tfn, const UnitTest &t, const modsecurity::Transaction &transaction) {
        auto ret = t.input;
        tfn.transform(ret, &transaction);
        return {1, ret};
    }

    static bool check(const UnitTestResult &result, const UnitTest &t) {
        return result.output != t.output;
    }
};


template<typename TestType>
UnitTestResult perform_unit_test_once(const UnitTest &t, modsecurity::Transaction &transaction) { // cppcheck-suppress constParameterReference ; transaction can be const for transformations but not for operators
    std::unique_ptr<typename TestType::ItemType> item(TestType::init(t));
    assert(item.get() != nullptr);

    return TestType::eval(*item.get(), t, transaction);
}


template<typename TestType>
UnitTestResult perform_unit_test_multithreaded(const UnitTest &t, modsecurity::Transaction &transaction) {

    constexpr auto NUM_THREADS = 50;
    constexpr auto ITERATIONS = 5'000;

    std::array<std::thread, NUM_THREADS> threads;
    std::array<UnitTestResult, NUM_THREADS> results;

    std::unique_ptr<typename TestType::ItemType> item(TestType::init(t));
    assert(item.get() != nullptr);

    for (auto i = 0; i != threads.size(); ++i)
    {
        auto &result = results[i];
        threads[i] = std::thread(
            [&item, &t, &result, &transaction]()
            {
                for (auto j = 0; j != ITERATIONS; ++j)
                    result = TestType::eval(*item.get(), t, transaction);
            });
    }

    UnitTestResult ret;

    for (auto i = 0; i != threads.size(); ++i)
    {
        threads[i].join();
        if (TestType::check(results[i], t))
            ret = results[i];   // error value, keep iterating to join all threads
        else if(i == 0)
            ret = results[i];   // initial value
    }

    return ret; // cppcheck-suppress uninitvar ; false positive, ret assigned at least once in previous loop
}


template<typename TestType>
void perform_unit_test_helper(const ModSecurityTest<UnitTest> &test, UnitTest &t,
    ModSecurityTestResults<UnitTest> &res, modsecurity::Transaction &transaction) {

    if (!test.m_test_multithreaded)
        t.result = perform_unit_test_once<TestType>(t, transaction);
    else
        t.result = perform_unit_test_multithreaded<TestType>(t, transaction);

    if (TestType::check(t.result, t)) {
        res.push_back(&t);
        if (test.m_automake_output) {
            std::cout << "FAIL ";
        }
    } else if (test.m_automake_output) {
        std::cout << "PASS ";
    }
}


void perform_unit_test(const ModSecurityTest<UnitTest> &test, UnitTest &t,
    ModSecurityTestResults<UnitTest> &res) {
    bool found = true;

    modsecurity_test::ModSecurityTestContext context("ModSecurity-unit v0.0.1-alpha"
                                                        " (ModSecurity unit test utility)");

    auto transaction = context.create_transaction();

    if (test.m_automake_output) {
        std::cout << ":test-result: ";
    }

    if (t.resource.empty() == false) {
        found = std::find(resources.begin(), resources.end(), t.resource)
            != resources.end();
    }

    if (!found) {
        t.skipped = true;
        res.push_back(&t);
        if (test.m_automake_output) {
            std::cout << "SKIP ";
        }
    }

    if (t.type == "op") {
        perform_unit_test_helper<OperatorTest>(test, t, res, transaction);
    } else if (t.type == "tfn") {
        perform_unit_test_helper<TransformationTest>(test, t, res, transaction);
    } else {
        std::cerr << "Failed. Test type is unknown: << " << t.type;
        std::cerr << std::endl;
    }

    if (test.m_automake_output) {
        std::cout << t.name << " "
            << modsecurity::utils::string::toHexIfNeeded(t.input)
            << std::endl;
    }
}


int main(int argc, char **argv) {
    int total = 0;
    ModSecurityTest<UnitTest> test;
    ModSecurityTestResults<UnitTest> results;

#if defined(WITH_GEOIP) or defined(WITH_MAXMIND)
    resources.push_back("geoip-or-maxmind");
#endif

#if defined(WITH_MAXMIND)
    resources.push_back("maxmind");
#endif

#if defined(WITH_GEOIP)
    resources.push_back("geoip");
#endif

#ifdef WITH_CURL
    resources.push_back("curl");
#endif
#ifdef WITH_SSDEEP
    resources.push_back("ssdeep");
#endif


    test.cmd_options(argc, argv);
    if (!test.m_automake_output) {
        std::cout << test.header();
    }

    test.load_tests();
    if (test.target == default_test_path) {
        test.load_tests("test-cases/secrules-language-tests/transformations");
    }

    for (auto& [filename, tests] : test) {
        total += tests.size();
        for (auto &t : tests) {
            ModSecurityTestResults<UnitTest> r;

            if (!test.m_automake_output) {
                std::cout << "  " << filename << "...\t";
            }
            perform_unit_test(test, *t, r);

            if (!test.m_automake_output) {
                int skp = 0;
                if (r.size() == 0) {
                    std::cout << KGRN << "0 tests failed.";
                } else {
                    for (const auto &i : r) {
                        if (i->skipped == true) {
                            skp++;
                        }
                    }
                    std::cout << KRED << r.size()-skp << " tests failed.";
                }
                std::cout << RESET;
                if (skp > 0) {
                    std::cout << " " << std::to_string(skp) << " ";
                    std::cout << "skipped.";
                }
                std::cout << std::endl;
            }

            results.insert(results.end(), r.begin(), r.end());
        }
    }

    if (!test.m_automake_output) {
        std::cout << "Total >> "  << total << std::endl;

        for (const auto t : results) {
            std::cout << t->print() << std::endl;
        }
    }

    const int skp = std::count_if(results.cbegin(), results.cend(), [](const auto &i)
                                    { return i->skipped; });
    const int failed = results.size() - skp;

    if (!test.m_automake_output) {
        std::cout << std::endl;

        std::cout << "Ran a total of: " << total << " unit tests - ";
        if (results.size() == 0) {
            std::cout << KGRN << "All tests passed" << RESET << std::endl;
        } else {
            std::cout << KRED << failed << " failed.";
            std::cout << RESET << std::endl;
            if (skp > 0) {
                std::cout << " " << std::to_string(skp) << " ";
                std::cout << "skipped.";
            }
        }
    }

    return failed;
}
