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

#include <modsecurity/modsecurity.h>
#include <modsecurity/transaction.h>
#include <modsecurity/rules.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/time.h>

#define FORKS 5
#define REQUESTS_PER_PROCESS 100


char main_rule_uri[] = "basic_rules.conf";
Rules *rules = NULL;
ModSecurity *modsec = NULL;


void process_special_request (int j) {
    Transaction *transaction;
    transaction = msc_new_transaction(modsec, rules, NULL);

    msc_process_connection(transaction, "127.0.0.1", 12345, "127.0.0.1", 80);
    msc_process_uri(transaction,
        "http://www.modsecurity.org/test?foo=herewego",
        "GET", "1.1");
    msc_add_request_header(transaction, "User-Agent",
        "Basic ModSecurity example");
    msc_process_request_headers(transaction);
    msc_process_request_body(transaction);
    msc_add_response_header(transaction, "Content-type", "text/html");
    msc_process_response_headers(transaction, 200, "HTTP 1.0");
    msc_process_response_body(transaction);
    msc_process_logging(transaction);
    msc_transaction_cleanup(transaction);
}

void process_request (int j) {
    int i;
    
    for (i = 0; i < REQUESTS_PER_PROCESS; i++) {
        if (i == 1 && j == 1) {
            process_special_request(j);
            continue;
        }
        struct timeval tv;

        Transaction *transaction;
        transaction = msc_new_transaction(modsec, rules, NULL);

        msc_process_connection(transaction, "127.0.0.1", 12345, "127.0.0.1", 80);
        msc_process_uri(transaction,
            "http://www.modsecurity.org/test?key1=value1&key2=value2&key3=value3",
            "GET", "1.1");
        msc_add_request_header(transaction, "User-Agent",
            "Basic ModSecurity example");
        msc_process_request_headers(transaction);
        msc_process_request_body(transaction);
        msc_add_response_header(transaction, "Content-type", "text/html");
        msc_process_response_headers(transaction, 200, "HTTP 1.0");
        msc_process_response_body(transaction);
        msc_process_logging(transaction);
        msc_transaction_cleanup(transaction);

        tv.tv_sec = 1;
        tv.tv_usec = 500;
        select(0, NULL, NULL, NULL, &tv);
    }
}


int main (int argc, char **argv)
{
    int ret;
    const char *error = NULL;
    int i = 0;
    pid_t pid;
    int f;

    modsec = msc_init();

    msc_set_connector_info(modsec, "ModSecurity-test v0.0.1-alpha (Simple " \
        "example on how to use ModSecurity API");

    rules = msc_create_rules_set();

    ret = msc_rules_add_file(rules, main_rule_uri, &error);
    if (ret < 0) {
        fprintf(stderr, "Problems loading the rules --\n");
        fprintf(stderr, "%s\n", error);
        goto end;
    }

    msc_rules_dump(rules);

    for (f = 0; f < FORKS; f++) {
        pid = fork();
        if (pid == 0) {
            process_request(f);
            goto child;
        }
        struct timeval tv;

        tv.tv_sec = 0;
        tv.tv_usec = 500;
        select(0, NULL, NULL, NULL, &tv);
    }

    wait(NULL);

child:

    if (pid == 0) {
        return 0;
    }
end:
    msc_rules_cleanup(rules);
    msc_cleanup(modsec);

    return 0;
}


