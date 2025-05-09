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

#ifndef WIN32
#include <unistd.h>
#else
#include <io.h>
#endif

#include <ctime>
#include <iostream>
#include <string>
#include <list>
#include <algorithm>
#include <cassert>

#include "modsecurity/rules_set.h"
#include "modsecurity/modsecurity.h"
#include "test/common/modsecurity_test.h"
#include "test/common/colors.h"
#include "test/regression/regression_test.h"
#include "test/common/modsecurity_test_results.h"
#include "test/common/modsecurity_test_context.h"
#include "src/utils/regex.h"

using modsecurity_test::CustomDebugLog;
using modsecurity_test::ModSecurityTest;
using modsecurity_test::ModSecurityTestResults;
using modsecurity_test::RegressionTest;
using modsecurity_test::RegressionTestResult;

using modsecurity::Utils::regex_search;
using modsecurity::Utils::SMatch;
using modsecurity::Utils::Regex;

std::string default_test_path = "test-cases/regression";
std::list<std::string> resources;

void print_help() {
    std::cout << "Use ./regression-tests /path/to/file" << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;
}

bool contains(const std::string &s, const std::string &pattern) {
    bool ret;
    modsecurity::Utils::Regex re(pattern);
    ret = modsecurity::Utils::regex_search(s, re);
    return ret;
}

void clearAuditLog(const std::string &filename) {
    if (!filename.empty()) {
        std::ofstream file{filename.c_str(), std::ofstream::out | std::ofstream::trunc};
        if (!file.is_open() || file.fail()) {
            std::cout << std::endl << "Failed to clear previous contents of audit log: " \
                << filename << std::endl;
        }
    }
}
std::string getAuditLogContent(const std::string &filename) {
    std::stringstream buffer;
    if (!filename.empty()) {
        try {
           std::ifstream t(filename);
           buffer << t.rdbuf();
        } catch (...) {
            std::cout << "Failed to read file:" << filename << std::endl;
        }
    }
    return buffer.str();
}


void actions(ModSecurityTestResults<RegressionTest> *r,
    modsecurity::Transaction *a, std::stringstream *serverLog) {
    modsecurity::ModSecurityIntervention it;
    memset(&it, '\0', sizeof(modsecurity::ModSecurityIntervention));
    it.status = 200;
    if (a->intervention(&it) == true) {
        if (it.pause != 0) {
            // FIXME:
        }
        if (it.status != 0) {
            r->status = it.status;
        }
        if (it.url != nullptr) {
            r->location.append(it.url);
	    free(it.url);
	    it.url = nullptr;
        }
        if (it.log != nullptr) {
            *serverLog << it.log;
            free(it.log);
            it.log = nullptr;
        }
    }
}

void perform_unit_test(const ModSecurityTest<RegressionTest> &test,
    const std::vector<std::unique_ptr<RegressionTest>> &tests,
    ModSecurityTestResults<RegressionTestResult> *res, int *count)
{
    for (auto &t : tests) {
        ModSecurityTestResults<RegressionTest> r;
        RegressionTestResult *testRes = new RegressionTestResult();

        testRes->test = t.get();
        r.status = 200;
        (*count)++;

        size_t offset = t->filename.find_last_of("/\\");
        std::string filename("");
        if (offset != std::string::npos) {
            filename = std::string(t->filename, offset + 1,
                t->filename.length() - offset - 1);
        } else {
            filename = t->filename;
        }

        if (!test.m_automake_output) {
            std::cout << std::setw(3) << std::right <<
                std::to_string(*count) << " ";
            std::cout << std::setw(50) << std::left << filename;
            std::cout << std::setw(70) << std::left << t->name;
        }

        if (t->enabled == 0) {
            if (test.m_automake_output) {
                std::cout << ":test-result: SKIP" << filename \
                    << ":" << t->name << std::endl;
            } else {
                std::cout << KCYN << "disabled" << RESET << std::endl;
            }
            res->push_back(testRes);
            testRes->disabled = true;
            testRes->reason << "JSON disabled";
            continue;
        }

#ifdef WITH_LMDB
        // some tests (e.g. issue-1831.json)  don't like it when data persists between runs
        unlink("./modsec-shared-collections");
        unlink("./modsec-shared-collections-lock");
#endif

        modsecurity_test::ModSecurityTestContext context("ModSecurity-regression v0.0.1-alpha" \
            " (ModSecurity regression test utility)");

        bool found = true;
        if (t->resource.empty() == false) {
            found = (std::find(resources.begin(), resources.end(), t->resource)
                != resources.end());
        }

        if (!found) {
            testRes->passed = false;
            testRes->skipped = true;
            testRes->reason << KCYN << "ModSecurity was not " << std::endl;
            testRes->reason << KCYN << "compiled with support " << std::endl;
            testRes->reason << KCYN << "to: " << t->resource << std::endl;
            testRes->reason << RESET << std::endl;
            if (test.m_automake_output) {
                std::cout << ":test-result: SKIP " << filename \
                    << ":" << t->name << std::endl;
            } else {
                std::cout << KCYN << "skipped!" << RESET << std::endl;
            }
            res->push_back(testRes);

            continue;
        }

        context.m_modsec_rules.load("SecDebugLogLevel 9");
        if (context.m_modsec_rules.load(t->rules.c_str(), filename) < 0) {
            /* Parser error */
            if (t->parser_error.empty() == true) {
                /*
                 * Not expecting any error, thus return the error to
                 * the user.
                 */
                if (test.m_automake_output) {
                    std::cout << ":test-result: FAIL " << filename \
                        << ":" << t->name << ":" << *count << std::endl;
                } else {
                    std::cout << KRED << "failed!" << RESET << std::endl;
                }
                testRes->reason << KRED << "parse failed." << RESET \
                    << std::endl;
                testRes->reason << context.m_modsec_rules.getParserError() \
                    << std::endl;
                testRes->passed = false;
                res->push_back(testRes);

                continue;
            }

            Regex re(t->parser_error);
            SMatch match;
            const auto s = context.m_modsec_rules.getParserError();

            if (regex_search(s, &match, re)) {
                if (test.m_automake_output) {
                    std::cout << ":test-result: PASS " << filename \
                        << ":" << t->name << std::endl;
                } else {
                    std::cout << KGRN << "passed!" << RESET << std::endl;
                }
                /* Parser error was expected, thus, the test passed. */
                testRes->reason << KGRN << "passed!" << RESET << std::endl;
                testRes->passed = true;
                res->push_back(testRes);

                continue;
            } else {
                /* Parser error was expected, but with a different content */
                if (test.m_automake_output) {
                    std::cout << ":test-result: FAIL " << filename \
                        << ":" << t->name << ":" << *count << std::endl;
                } else {
                    std::cout << KRED << "failed!" << RESET << std::endl;
                }

                testRes->reason << KRED << "failed!" << RESET << std::endl;
                testRes->reason << KWHT << "Expected a parser error." \
                    << RESET << std::endl;
                testRes->reason << KWHT << "Expected: " << RESET \
                    << t->parser_error << std::endl;
                testRes->reason << KWHT << "Produced: " << RESET \
                    << s << std::endl;
                testRes->passed = false;
                res->push_back(testRes);

                continue;
            }
        } else {
            /* Parser error was expected but never happened */
            if (t->parser_error.empty() == false) {
                if (test.m_automake_output) {
                    std::cout << ":test-result: FAIL " << filename \
                        << ":" << t->name << ":" << *count << std::endl;
                } else {
                    std::cout << KRED << "failed!" << RESET << std::endl;
                    std::cout << KWHT << "Expected a parser error." \
                        << RESET << std::endl;
                    std::cout << KWHT << "Expected: " << RESET \
                        << t->parser_error << std::endl;
                }
                testRes->passed = false;
                res->push_back(testRes);

                continue;
            }
        }

        auto modsec_transaction = context.create_transaction();

        if (t->hostname != "") {
            modsec_transaction.setRequestHostName(t->hostname);
        }

        clearAuditLog(modsec_transaction.m_rules->m_auditLog->m_path1);

        modsec_transaction.processConnection(t->clientIp.c_str(),
            t->clientPort, t->serverIp.c_str(), t->serverPort);

        actions(&r, &modsec_transaction, &context.m_server_log);

        modsec_transaction.processURI(t->uri.c_str(), t->method.c_str(),
            t->httpVersion.c_str());

        actions(&r, &modsec_transaction, &context.m_server_log);

        for (const auto &[name, value] : t->request_headers) {
            modsec_transaction.addRequestHeader(name.c_str(),
                value.c_str());
        }

        modsec_transaction.processRequestHeaders();
        actions(&r, &modsec_transaction, &context.m_server_log);

        modsec_transaction.appendRequestBody(
            (unsigned char *)t->request_body.c_str(),
            t->request_body.size());
        modsec_transaction.processRequestBody();
        actions(&r, &modsec_transaction, &context.m_server_log);

        for (const auto &[name, value] : t->response_headers) {
            modsec_transaction.addResponseHeader(name.c_str(),
                value.c_str());
        }

        modsec_transaction.processResponseHeaders(r.status,
            t->response_protocol);
        actions(&r, &modsec_transaction, &context.m_server_log);

        modsec_transaction.appendResponseBody(
            (unsigned char *)t->response_body.c_str(),
            t->response_body.size());
        modsec_transaction.processResponseBody();
        actions(&r, &modsec_transaction, &context.m_server_log);

        modsec_transaction.processLogging();

        const auto *d = static_cast<CustomDebugLog *>(context.m_modsec_rules.m_debugLog);

        if (!d->contains(t->debug_log)) {
            if (test.m_automake_output) {
                std::cout << ":test-result: FAIL " << filename \
                    << ":" << t->name << ":" << *count << std::endl;
            } else {
                std::cout << KRED << "failed!" << RESET << std::endl;
            }
            testRes->reason << "Debug log was not matching the " \
                << "expected results." << std::endl;
            testRes->reason << KWHT << "Expecting: " << RESET
                << t->debug_log + "";
            testRes->passed = false;
        } else if (r.status != t->http_code) {
            if (test.m_automake_output) {
                std::cout << ":test-result: FAIL " << filename \
                    << ":" << t->name << ":" << *count << std::endl;
            } else {
                std::cout << KRED << "failed!" << RESET << std::endl;
            }
            testRes->reason << "HTTP code mismatch. expecting: " +
                std::to_string(t->http_code) +
                " got: " + std::to_string(r.status) + "\n";
            testRes->passed = false;
        } else if (!contains(context.m_server_log.str(), t->error_log)) {
            if (test.m_automake_output) {
                std::cout << ":test-result: FAIL " << filename \
                    << ":" << t->name << std::endl;
            } else {
                std::cout << KRED << "failed!" << RESET << std::endl;
            }
            testRes->reason << "Error log was not matching the " \
                << "expected results." << std::endl;
            testRes->reason << KWHT << "Expecting: " << RESET \
                << t->error_log + "";
            testRes->passed = false;
        } else if (!t->audit_log.empty() && !contains(getAuditLogContent(modsec_transaction.m_rules->m_auditLog->m_path1), t->audit_log)) {
            if (test.m_automake_output) {
                std::cout << ":test-result: FAIL " << filename \
                    << ":" << t->name << ":" << *count << std::endl;
            } else {
                std::cout << KRED << "failed!" << RESET << std::endl;
            }
            testRes->reason << "Audit log was not matching the " \
                << "expected results." << std::endl;
            testRes->reason << KWHT << "Expecting: " << RESET \
                << t->audit_log + "";
            testRes->passed = false;
        } else {
            if (test.m_automake_output) {
                std::cout << ":test-result: PASS " << filename \
                    << ":" << t->name << std::endl;
            } else  {
                std::cout << KGRN << "passed!" << RESET << std::endl;
            }
            testRes->passed = true;
        }

        if (testRes->passed == false) {
            testRes->reason << std::endl;
            testRes->reason << KWHT << "Debug log:" << RESET << std::endl;
            testRes->reason << d->log_messages() << std::endl;
            testRes->reason << KWHT << "Error log:" << RESET << std::endl;
            testRes->reason << context.m_server_log.str() << std::endl;
            testRes->reason << KWHT << "Audit log:" << RESET << std::endl;
            testRes->reason << getAuditLogContent(modsec_transaction.m_rules->m_auditLog->m_path1) << std::endl;
        }

        r.log_raw_debug_log = d->log_messages();

        res->push_back(testRes);
    }
}

int main(int argc, char **argv)
{
    ModSecurityTest<RegressionTest> test;

    std::string ver(MODSECURITY_VERSION);
    std::string envvar("ModSecurity " + ver + " regression tests");

#ifndef WIN32
    setenv("MODSECURITY", envvar.c_str(), 1);
#else
    _putenv_s("MODSECURITY", envvar.c_str());
#endif

#ifndef NO_LOGS
    int test_number = 0;
#endif

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
#ifdef WITH_LUA
    resources.push_back("lua");
#endif
#ifdef WITH_LIBXML2
    resources.push_back("libxml2");
#endif

#ifdef NO_LOGS
    std::cout << "Test utility cannot work without logging support." \
        << std::endl;
    return 0;
#else
    test.cmd_options(argc, argv);
    if (!test.m_automake_output && !test.m_count_all) {
        std::cout << test.header();
    }

    test.load_tests();

    if (!test.m_automake_output && !test.m_count_all) {
        std::cout << std::setw(4) << std::right << "# ";
        std::cout << std::setw(50) << std::left << "File Name";
        std::cout << std::setw(70) << std::left << "Test Name";
        std::cout << std::setw(10) << std::left << "Passed?";
        std::cout << std::endl;
        std::cout << std::setw(4) << std::right << "--- ";
        std::cout << std::setw(50) << std::left << "---------";
        std::cout << std::setw(70) << std::left << "---------";
        std::cout << std::setw(10) << std::left << "-------";
        std::cout << std::endl;
    }
    int counter = 0;

    std::list<std::string> keyList;
    for (const auto &[name, tests] : test) {
        keyList.push_back(name);
    }
    keyList.sort();

    if (test.m_count_all) {
        std::cout << std::to_string(keyList.size()) << std::endl;
        exit(0);
    }

    ModSecurityTestResults<RegressionTestResult> res;
    for (const std::string &a : keyList) {
        test_number++;
        if ((test.m_test_number == 0)
            || (test_number == test.m_test_number)) {
            const auto &tests = test[a];
            perform_unit_test(test, tests, &res, &counter);
        }
    }

    std::cout << std::endl;

    int passed = 0;
    int failed = 0;
    int disabled = 0;
    int skipped = 0;

    for (RegressionTestResult *r : res) {
        if (r->skipped == true) {
            skipped++;
        }
        if (r->disabled == true) {
            disabled++;
        }
        if (r->passed == true) {
            passed++;
        }

        if (!r->passed && !r->skipped && !r->disabled) {
            if (!test.m_automake_output) {
                std::cout << KRED << "Test failed." << RESET << KWHT \
                    << " From: " \
                    << RESET << r->test->filename << "." << std::endl;
                std::cout << KWHT << "Test name: " << RESET \
                    << r->test->name \
                    << "." << std::endl;
                std::cout << KWHT << "Reason: " << RESET << std::endl;
                std::cout << r->reason.str() << std::endl;
            }
            failed++;
        }
        delete r;
    }

    if (!test.m_automake_output) {
        std::cout << "Ran a total of: " << std::to_string(failed + passed) \
            << " regression tests - ";
        if (failed == 0) {
            std::cout << KGRN << "All tests passed. " << RESET;
        } else {
            std::cout << KRED << failed << " failed. " << RESET;
        }

        std::cout << KCYN << std::to_string(skipped) << " ";
        std::cout << "skipped test(s). " << std::to_string(disabled) << " ";
        std::cout << "disabled test(s)." << RESET << std::endl;
    }

    return failed;
#endif
}
