/**
 * Copyright 2012, 2013, 2014 Nick Galbreath
 * nickg@client9.com
 * BSD License -- see COPYING.txt for details
 *
 * This is for testing against files in ../data/ *.txt
 * Reads from stdin or a list of files, and emits if a line
 * is a SQLi attack or not, and does basic statistics
 *
 */
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>

#include "libinjection_html5.h"
#include "libinjection_xss.h"
#include "libinjection.h"

int urlcharmap(char ch);
size_t modp_url_decode(char* dest, const char* s, size_t len);
const char* h5_type_to_string(enum html5_type x);
void print_html5_token(h5_state_t* hs);

int urlcharmap(char ch) {
    switch (ch) {
    case '0': return 0;
    case '1': return 1;
    case '2': return 2;
    case '3': return 3;
    case '4': return 4;
    case '5': return 5;
    case '6': return 6;
    case '7': return 7;
    case '8': return 8;
    case '9': return 9;
    case 'a': case 'A': return 10;
    case 'b': case 'B': return 11;
    case 'c': case 'C': return 12;
    case 'd': case 'D': return 13;
    case 'e': case 'E': return 14;
    case 'f': case 'F': return 15;
    default:
        return 256;
    }
}

size_t modp_url_decode(char* dest, const char* s, size_t len)
{
    const char* deststart = dest;

    size_t i = 0;
    int d = 0;
    while (i < len) {
        switch (s[i]) {
        case '+':
            *dest++ = ' ';
            i += 1;
            break;
        case '%':
            if (i+2 < len) {
                d = (urlcharmap(s[i+1]) << 4) | urlcharmap(s[i+2]);
                if ( d < 256) {
                    *dest = (char) d;
                    dest++;
                    i += 3; /* loop will increment one time */
                } else {
                    *dest++ = '%';
                    i += 1;
                }
            } else {
                *dest++ = '%';
                i += 1;
            }
            break;
        default:
            *dest++ = s[i];
            i += 1;
        }
    }
    *dest = '\0';
    return (size_t)(dest - deststart); /* compute "strlen" of dest */
}

const char* h5_type_to_string(enum html5_type x)
{
    switch (x) {
    case DATA_TEXT: return "DATA_TEXT";
    case TAG_NAME_OPEN: return "TAG_NAME_OPEN";
    case TAG_NAME_CLOSE: return "TAG_NAME_CLOSE";
    case TAG_NAME_SELFCLOSE: return "TAG_NAME_SELFCLOSE";
    case TAG_DATA: return "TAG_DATA";
    case TAG_CLOSE: return "TAG_CLOSE";
    case ATTR_NAME: return "ATTR_NAME";
    case ATTR_VALUE: return "ATTR_VALUE";
    case TAG_COMMENT: return "TAG_COMMENT";
    case DOCTYPE: return "DOCTYPE";
    default:
        assert(0);
    }
}

void print_html5_token(h5_state_t* hs)
{
    char* tmp = (char*) malloc(hs->token_len + 1);
    memcpy(tmp, hs->token_start, hs->token_len);
    /* TODO.. encode to be printable */
    tmp[hs->token_len] = '\0';

    printf("%s,%d,%s\n",
           h5_type_to_string(hs->token_type),
           (int) hs->token_len,
           tmp);

    free(tmp);
}

int main(int argc, const char* argv[])
{
    size_t slen;
    h5_state_t hs;
    char* copy;
    int offset = 1;
    int flag = 0;
    int urldecode = 0;

    if (argc < 2) {
        fprintf(stderr, "need more args\n");
        return 1;
    }

    while (offset < argc) {
      if (strcmp(argv[offset], "-u") == 0) {
            offset += 1;
            urldecode = 1;

      } else if (strcmp(argv[offset], "-f") == 0) {
            offset += 1;
            flag = atoi(argv[offset]);
            offset += 1;
      } else {
        break;
      }
    }

    /* ATTENTION: argv is a C-string, null terminated.  We copy this
     * to it's own location, WITHOUT null byte.  This way, valgrind
     * can see if we run past the buffer.
     */

    slen = strlen(argv[offset]);
    copy = (char* ) malloc(slen);
    memcpy(copy, argv[offset], slen);
    if (urldecode) {
      slen = modp_url_decode(copy, copy, slen);
    }

    libinjection_h5_init(&hs, copy, slen, (enum html5_flags) flag);
    while (libinjection_h5_next(&hs)) {
        print_html5_token(&hs);
    }

    if (libinjection_is_xss(copy, slen, flag)) {
      printf("is injection!\n");
    }
    free(copy);
    return 0;
}
