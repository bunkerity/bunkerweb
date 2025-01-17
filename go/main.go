/*
 * Copyright (c) 2013 Radolsaw Wesolowski
 *
 * Permission to use, copy, modify, and distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 */

package main

/*
#cgo CFLAGS: -I./libinjection
#cgo LDFLAGS: -L./libinjection -linjection
#include "libinjection.h"
#include "libinjection_sqli.h"
#include <stdlib.h>
*/
import "C"
import (
	"bytes"
	"fmt"
	"unsafe"
)

func main() {
	sqlinjection := "asdf asd ; -1' and 1=1 union/* foo */select load_file('/etc/passwd')--"
	var out [8]C.char
	pointer := (*C.char)(unsafe.Pointer(&out[0]))
	inputcChar := C.CString(sqlinjection)
	defer C.free(unsafe.Pointer(inputcChar))
	if found := C.libinjection_sqli(inputcChar, C.size_t(len(sqlinjection)), pointer); found == 1 {
		output := C.GoBytes(unsafe.Pointer(&out[0]), 8)
		fmt.Printf("sqli with fingerprint of '%s'\n", string(output[:bytes.Index(output, []byte{0})]))
	}
}
