#ifndef LIBINJECTION_HTML5
#define LIBINJECTION_HTML5

#ifdef __cplusplus
extern "C" {
#endif

/* pull in size_t */

#include <stddef.h>

enum html5_type {
    DATA_TEXT,
    TAG_NAME_OPEN,
    TAG_NAME_CLOSE,
    TAG_NAME_SELFCLOSE,
    TAG_DATA,
    TAG_CLOSE,
    ATTR_NAME,
    ATTR_VALUE,
    TAG_COMMENT,
    DOCTYPE
};

enum html5_flags {
    DATA_STATE,
    VALUE_NO_QUOTE,
    VALUE_SINGLE_QUOTE,
    VALUE_DOUBLE_QUOTE,
    VALUE_BACK_QUOTE
};

struct h5_state;
typedef int (*ptr_html5_state)(struct h5_state *);

typedef struct h5_state {
    const char *s;
    size_t len;
    size_t pos;
    int is_close;
    ptr_html5_state state;
    const char *token_start;
    size_t token_len;
    enum html5_type token_type;
} h5_state_t;

void libinjection_h5_init(h5_state_t *hs, const char *s, size_t len,
                          enum html5_flags);
int libinjection_h5_next(h5_state_t *hs);

#ifdef __cplusplus
}
#endif
#endif
