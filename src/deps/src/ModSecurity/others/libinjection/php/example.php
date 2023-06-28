<?php

// add to your ini file:
// extension=YOUR DIRECTORY//libinjection.so

echo "Using libinjection " . LIBINJECTION_VERSION . "\n";

// make a state object .. can be reused
$x = new_libinjection_sqli_state();

// pass it in to init
// arg 1 -- state objection above
// arg 2 -- php string of input -- MUST BE URL-DECODED
// arg 3 -- flags -- just pass in '0' for now
$input = "1 union select 1,2,3,4--";
libinjection_sqli_init($x, $input, 0);

// do a test
$sqli = libinjection_is_sqli($x);
if ($sqli == 1) {
  echo "sqli with fingerprint " .  libinjection_sqli_state_fingerprint_get($x) . "\n";
} else {
  echo "not sqli";
}

