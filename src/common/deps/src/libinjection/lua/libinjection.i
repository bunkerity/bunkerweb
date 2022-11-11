/* libinjection.i SWIG interface file */
%module libinjection
%{
#include "libinjection.h"
#include "libinjection_sqli.h"

static char libinjection_lua_lookup_word(sfilter* sf, int lookup_type,
                                         const char* s, size_t len)
{
    lua_State* L = (lua_State*) sf->userdata;
    //char* luafunc = (char *)lua_tostring(L, 2);
    lua_getglobal(L, "lookup_word");
    SWIG_NewPointerObj(L, (void*)sf, SWIGTYPE_p_libinjection_sqli_state, 0);
    lua_pushnumber(L, lookup_type);
    lua_pushlstring(L, s, len);

    if (lua_pcall(L, 3, 1, 0)) {
        printf("Something bad happened");
    }

    const char* result = lua_tostring(L, -1);
    if (result == NULL) {
        return 0;
    } else {
        return result[0];
    }
}
%}
%include "typemaps.i"


// The C functions all start with 'libinjection_' as a namespace
// We don't need this since it's in the libinjection table
// i.e. libinjection.libinjection_is_sqli --> libinjection.is_sqli
 //
%rename("%(strip:[libinjection_])s") "";

%typemap(in) (ptr_lookup_fn fn, void* userdata) {
    if (lua_isnil(L, 1)) {
        arg2 = NULL;
        arg3 = NULL;
    } else {
        arg2 = libinjection_lua_lookup_word;
        arg3 = (void *) L;
    }
 }


%typemap(out) stoken_t [ANY] {
    int i;
    lua_newtable(L);
    for (i = 0; i < $1_dim0; i++) {
        lua_pushnumber(L, i+1);
        SWIG_NewPointerObj(L, (void*)(& $1[i]), SWIGTYPE_p_stoken_t,0);
        lua_settable(L, -3);
    }
    SWIG_arg += 1;
}


%include "libinjection.h"
%include "libinjection_sqli.h"
