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

#include <unistd.h>

#include <string>
#include <memory>


#define NUM_THREADS 100


char request_header[] =  "" \
    "GET /tutorials/other/top-20-mysql-best-practices/ HTTP/1.1\n\r" \
    "Host: net.tutsplus.com\n\r" \
    "User-Agent: Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.5)" \
    " Gecko/20091102 Firefox/3.5.5 (.NET CLR 3.5.30729)\n\r" \
    "Accept: text/html,application/xhtml+xml,application/xml; " \
    "q=0.9,*/*;q=0.8\n\r" \
    "Accept-Language: en-us,en;q=0.5\n\r" \
    "Accept-Encoding: gzip,deflate\n\r" \
    "Accept-Charset: ISO-8859-1,utf-8;q=0.7,*;q=0.7\n\r" \
    "Keep-Alive: 300\n\r" \
    "Connection: keep-alive\n\r" \
    "Cookie: PHPSESSID=r2t5uvjq435r4q7ib3vtdjq120\n\r" \
    "Pragma: no-cache\n\r" \
    "Cache-Control: no-cache\n\r";

char request_uri[] = "/test.pl?param1=test&para2=test2";

char request_body[] = "";

char response_headers[] = "" \
    "HTTP/1.1 200 OK\n\r" \
    "Content-Type: text/xml; charset=utf-8\n\r" \
    "Content-Length: length\n\r";

char response_body[] = "" \
    "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n\r" \
    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" " \
    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" " \
    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">\n\r" \
    "  <soap:Body>\n\r" \
    "  <EnlightenResponse xmlns=\"http://clearforest.com/\">\n\r" \
    "  <EnlightenResult>string</EnlightenResult>\n\r" \
    "  </EnlightenResponse>\n\r" \
    "  </soap:Body>\n\r" \
    "</soap:Envelope>\n\r";

char ip[] = "200.249.12.31";

#include "modsecurity/rule_message.h"

#ifndef EXAMPLES_READING_LOGS_VIA_RULE_MESSAGE_READING_LOGS_VIA_RULE_MESSAGE_H_
#define EXAMPLES_READING_LOGS_VIA_RULE_MESSAGE_READING_LOGS_VIA_RULE_MESSAGE_H_


struct data_ms {
    modsecurity::ModSecurity *modsec;
    modsecurity::Rules *rules;
};


static void *process_request(void *data) {
    struct data_ms *a = (struct data_ms *)data;
    modsecurity::ModSecurity *modsec = a->modsec;
    modsecurity::Rules *rules = a->rules;
    int z = 0;

    for (z = 0; z < 10000; z++) {
        modsecurity::Transaction *modsecTransaction = \
            new modsecurity::Transaction(modsec, rules, NULL);
        modsecTransaction->processConnection(ip, 12345, "127.0.0.1", 80);
        modsecTransaction->processURI(request_uri, "GET", "1.1");

        usleep(10);
        modsecTransaction->addRequestHeader("Host",
            "net.tutsplus.com");
        modsecTransaction->processRequestHeaders();
        modsecTransaction->processRequestBody();
        modsecTransaction->addResponseHeader("HTTP/1.1",
            "200 OK");
        modsecTransaction->processResponseHeaders(200, "HTTP 1.2");
        modsecTransaction->appendResponseBody(
            (const unsigned char*)response_body,
            strlen((const char*)response_body));
        modsecTransaction->processResponseBody();
        modsecTransaction->processLogging();

        delete modsecTransaction;
    }

    pthread_exit(NULL);
    return NULL;
}


class ReadingLogsViaRuleMessage {
 public:
    ReadingLogsViaRuleMessage(char *request_header,
        char *request_uri,
        char *request_body,
        char *response_headers,
        char *response_body,
        char *ip,
        std::string rules) :
            m_request_header(request_header),
            m_request_uri(request_uri),
            m_request_body(request_body),
            m_response_headers(response_headers),
            m_response_body(response_body),
            m_ip(ip),
            m_rules(rules)
        { }

    int process() {
        pthread_t threads[NUM_THREADS];
        int i;
        struct data_ms dms;
        void *status;

        modsecurity::ModSecurity *modsec;
        modsecurity::Rules *rules;
        modsecurity::ModSecurityIntervention it;

        modsec = new modsecurity::ModSecurity();
        modsec->setConnectorInformation("ModSecurity-test v0.0.1-alpha" \
            " (ModSecurity test)");
        modsec->setServerLogCb(logCb, modsecurity::RuleMessageLogProperty
            | modsecurity::IncludeFullHighlightLogProperty);

        rules = new modsecurity::Rules();
        if (rules->loadFromUri(m_rules.c_str()) < 0) {
            std::cout << "Problems loading the rules..." << std::endl;
            std::cout << rules->m_parserError.str() << std::endl;
            return -1;
        }

        dms.modsec = modsec;
        dms.rules = rules;

        for (i = 0; i < NUM_THREADS; i++) {
            pthread_create(&threads[i], NULL, process_request,
		reinterpret_cast<void *>(&dms));
            //  process_request((void *)&dms);
        }

        usleep(10000);

        for (i=0; i < NUM_THREADS; i++) {
            pthread_join(threads[i], &status);
            std::cout << "Main: completed thread id :" << i << std::endl;
        }

        delete rules;
        delete modsec;
        pthread_exit(NULL);
        return 0;
end:
        return -1;
    }

    static void logCb(void *data, const void *ruleMessagev) {
        if (ruleMessagev == NULL) {
            std::cout << "I've got a call but the message was null ;(";
            std::cout << std::endl;
            return;
        }

        const modsecurity::RuleMessage *ruleMessage = \
            reinterpret_cast<const modsecurity::RuleMessage *>(ruleMessagev);

        std::cout << "Rule Id: " << std::to_string(ruleMessage->m_ruleId);
        std::cout << " phase: " << std::to_string(ruleMessage->m_phase);
        std::cout << std::endl;
        if (ruleMessage->m_isDisruptive) {
            std::cout << " * Disruptive action: ";
            std::cout << modsecurity::RuleMessage::log(ruleMessage);
            std::cout << std::endl;
            std::cout << " ** %d is meant to be informed by the webserver.";
            std::cout << std::endl;
        } else {
            std::cout << " * Match, but no disruptive action: ";
            std::cout << modsecurity::RuleMessage::log(ruleMessage);
            std::cout << std::endl;
        }
    }

 protected:
    char *m_request_header;
    char *m_request_uri;
    char *m_request_body;
    char *m_response_headers;
    char *m_response_body;
    char *m_ip;
    std::string m_rules;
};

#endif  // EXAMPLES_READING_LOGS_VIA_RULE_MESSAGE_READING_LOGS_VIA_RULE_MESSAGE_H_
