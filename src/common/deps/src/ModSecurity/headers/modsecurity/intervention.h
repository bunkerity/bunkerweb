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

#ifndef HEADERS_MODSECURITY_INTERVENTION_H_
#define HEADERS_MODSECURITY_INTERVENTION_H_

#ifdef __cplusplus
namespace modsecurity {
#endif

typedef struct ModSecurityIntervention_t {
    int status;
    int pause;
    char *url;
    char *log;
    int disruptive;
} ModSecurityIntervention;

#ifdef __cplusplus
namespace intervention {
    static void reset(ModSecurityIntervention_t *i) {
        i->status = 200;
        i->pause = 0;
        i->disruptive = 0;
    }

    static void clean(ModSecurityIntervention_t *i) {
        i->url = NULL;
        i->log = NULL;
        reset(i);
    }

    static void freeUrl(ModSecurityIntervention_t *i) {
        if (i->url) {
            free(i->url);
            i->url = NULL;
        }
    }

    static void freeLog(ModSecurityIntervention_t *i) {
        if (i->log) {
            free(i->log);
            i->log = NULL;
        }
    }

    static void free(ModSecurityIntervention_t *i) {
        freeUrl(i);
        freeLog(i);
    }

}  // namespace intervention
#endif

#ifdef __cplusplus
}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_INTERVENTION_H_
