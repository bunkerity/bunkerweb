/* libinjection.i SWIG interface file */
%module libinjection
%{
#include "libinjection.h"
#include "libinjection_sqli.h"
#include <stddef.h>

/* This is the callback function that runs a python function
 *
 */
static char libinjection_python_check_fingerprint(sfilter* sf, int lookuptype, const char* word, size_t len)
{
    PyObject *fp;
    PyObject *arglist;
    PyObject *result;
    const char* strtype;
    char ch;

    // get sfilter->pattern
    // convert to python string
    fp = SWIG_InternalNewPointerObj((void*)sf, SWIGTYPE_p_libinjection_sqli_state,0);

    arglist = Py_BuildValue("(Nis#)", fp, lookuptype, word, len);
    // call pyfunct with string arg
    result = PyObject_CallObject((PyObject*) sf->userdata, arglist);
    Py_DECREF(arglist);
    if (result == NULL) {
        printf("GOT NULL\n");
        // python call has an exception
        // pass it back
        ch = '\0';
    } else {
        // convert value of python call to a char
        strtype =  PyString_AsString(result);
        ch = strtype[0];
        Py_DECREF(result);
    }
    return ch;
}

%}
%include "typemaps.i"

// The C functions all start with 'libinjection_' as a namespace
// We don't need this since it's in the libinjection python package
// i.e. libinjection.libinjection_is_sqli --> libinjection.is_sqli
 //
%rename("%(strip:[libinjection_])s") "";

// SWIG doesn't natively support fixed sized arrays.
// this typemap converts the fixed size array sfilter.tokevec
// into a list of pointers to stoken_t types. In otherword this code makes this example work
// s = sfilter()
// libinjection_is_sqli(s, "a string",...)
// for i in len(s.pat):
//   print s.tokevec[i].val
//

%typemap(out) stoken_t [ANY] {
int i;
$result = PyList_New($1_dim0);
for (i = 0; i < $1_dim0; i++) {
    PyObject *o =  SWIG_NewPointerObj((void*)(& $1[i]), SWIGTYPE_p_stoken_t,0);
    PyList_SetItem($result,i,o);
}
}

// automatically append string length into arg array
%apply (char *STRING, size_t LENGTH) { (const char *s, size_t slen) };

%typemap(in) (ptr_lookup_fn fn, void* userdata) {
    if ($input == Py_None) {
        $1 = NULL;
        $2 = NULL;
    } else {
        $1 = libinjection_python_check_fingerprint;
        $2 = $input;
    }
}
%include "libinjection.h"
%include "libinjection_sqli.h"
