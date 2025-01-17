/* libinjection.i SWIG interface file for PHP */
%module libinjection
%{
#include "libinjection.h"
#include "libinjection_sqli.h"

struct libinjection_sqli_token * libinjection_sqli_state_tokenvec_geti(sfilter* sf, int i) {
    return &(sf->tokenvec[i]);
}
%}

%include "typemaps.i"

// automatically append string length into arg array
%apply (char *STRING, size_t LENGTH) { (const char *s, size_t slen) };

%include "libinjection.h"
%include "libinjection_sqli.h"