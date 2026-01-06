/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/utils/https_client.h"
#include "src/config.h"

#ifdef MSC_WITH_CURL
#include <curl/curl.h>
#endif

#ifndef WIN32
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#else
#include <WinSock2.h>
#endif
#include <string>

#include <fstream>
#include <iostream>

#include "modsecurity/modsecurity.h"
#include "src/unique_id.h"

namespace modsecurity {
namespace Utils {


size_t HttpsClient::handle(char * data, size_t size, size_t nmemb, void * p) {
    return static_cast<HttpsClient*>(p)->handle_impl(data, size, nmemb);
}


size_t HttpsClient::handle_impl(char* data, size_t size, size_t nmemb) {
    content.append(data, size * nmemb);
    return size * nmemb;
}

void HttpsClient::setKey(const std::string& key) {
    m_key = "ModSec-key: " + key;
}

void HttpsClient::setRequestBody(const std::string& requestBody) {
    m_requestBody = requestBody;
}

void HttpsClient::setRequestType(const std::string& requestType) {
    m_requestType = requestType;
}


#ifdef MSC_WITH_CURL
bool HttpsClient::download(const std::string &uri) {
    CURL *curl;
    CURLcode res;
    std::string uniqueId = "ModSec-unique-id: " + UniqueId::uniqueId();
    std::string status = "ModSec-status: " + std::to_string(MODSECURITY_VERSION_NUM);

    curl = curl_easy_init();
    if (!curl) {
        error = "Not able to initialize libcurl";
        return false;
    }

    struct curl_slist *headers_chunk = NULL;
    curl_easy_setopt(curl, CURLOPT_URL, uri.c_str());

    headers_chunk = curl_slist_append(headers_chunk, uniqueId.c_str());
    headers_chunk = curl_slist_append(headers_chunk, status.c_str());

    if (m_requestType.empty() == false) {
        std::string hdr = "Content-Type: " + m_requestType;
        headers_chunk = curl_slist_append(headers_chunk, hdr.c_str());
    }

    if (m_key.empty() == false) {
        headers_chunk = curl_slist_append(headers_chunk, m_key.c_str());
    }

    /* Make it TLS 1.2 at least. */
    curl_easy_setopt(curl, CURLOPT_SSLVERSION, CURL_SSLVERSION_TLSv1_2);

    /* those are the default options, but lets make sure */
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 1);

#ifdef WIN32
    /* use the operating system's native CA store for certificate verification.*/
    curl_easy_setopt(curl, CURLOPT_SSL_OPTIONS, (long)CURLSSLOPT_NATIVE_CA);
#endif

    /* send all data to this function  */
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, &HttpsClient::handle);

    /* we pass our 'chunk' struct to the callback function */
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, this);

    curl_easy_setopt(curl, CURLOPT_USERAGENT, "ModSecurity3");

    /* We want Curl to return error in case there is an HTTP error code */
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1);

    if (m_requestBody.empty() == false) {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, m_requestBody.c_str());
        headers_chunk = curl_slist_append(headers_chunk, "Expect:"); // Disable Expect: 100-continue
    }

    /* set HTTP headers for request */
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers_chunk);

    res = curl_easy_perform(curl);

    curl_slist_free_all(headers_chunk);

    if (res != CURLE_OK) {
        error = curl_easy_strerror(res);
    }

    curl_easy_cleanup(curl);

    return res == CURLE_OK;
}
#else
bool HttpsClient::download(const std::string &uri) {
    error = "Not compiled with libcurl support";
    return false;
}
#endif

}  // namespace Utils
}  // namespace modsecurity

