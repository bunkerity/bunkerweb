<?php
function print_token($tok) {
    $tt = libinjection_sqli_token_type_get($tok);
    $out = '';
    $out .= $tt;
    $out .= ' ';
    if ($tt == 's') {
        $out .= print_token_string($tok);
    } else if ($tt == 'v') {
        $vc = libinjection_sqli_token_count_get($tok);
        if ($vc == 1) {
            $out .= '@';
        } else if ($vc == 2) {
            $out .= '@@';
        }
        $out .= print_token_string($tok);
    } else {
        $out .= libinjection_sqli_token_val_get($tok);
    }
    return trim($out);
}

function print_token_string($tok) {
   $out = '';
   $quote = libinjection_sqli_token_str_open_get($tok);
   if ($quote != "\0") {
       $out .= $quote;
   }
   $out .= libinjection_sqli_token_val_get($tok);
   $quote = libinjection_sqli_token_str_close_get($tok);
   if ($quote != "\0") {
       $out .= $quote;
   }
   return $out;
}