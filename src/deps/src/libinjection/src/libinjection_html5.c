#include "libinjection_html5.h"

#include <string.h>
#include <assert.h>

#ifdef DEBUG
#include <stdio.h>
#define TRACE() printf("%s:%d\n", __FUNCTION__, __LINE__)
#else
#define TRACE()
#endif


#define CHAR_EOF -1
#define CHAR_NULL 0
#define CHAR_BANG 33
#define CHAR_DOUBLE 34
#define CHAR_PERCENT 37
#define CHAR_SINGLE 39
#define CHAR_DASH 45
#define CHAR_SLASH 47
#define CHAR_LT 60
#define CHAR_EQUALS 61
#define CHAR_GT 62
#define CHAR_QUESTION 63
#define CHAR_RIGHTB 93
#define CHAR_TICK 96

/* prototypes */

static int h5_skip_white(h5_state_t* hs);
static int h5_is_white(char ch);
static int h5_state_eof(h5_state_t* hs);
static int h5_state_data(h5_state_t* hs);
static int h5_state_tag_open(h5_state_t* hs);
static int h5_state_tag_name(h5_state_t* hs);
static int h5_state_tag_name_close(h5_state_t* hs);
static int h5_state_end_tag_open(h5_state_t* hs);
static int h5_state_self_closing_start_tag(h5_state_t* hs);
static int h5_state_attribute_name(h5_state_t* hs);
static int h5_state_after_attribute_name(h5_state_t* hs);
static int h5_state_before_attribute_name(h5_state_t* hs);
static int h5_state_before_attribute_value(h5_state_t* hs);
static int h5_state_attribute_value_double_quote(h5_state_t* hs);
static int h5_state_attribute_value_single_quote(h5_state_t* hs);
static int h5_state_attribute_value_back_quote(h5_state_t* hs);
static int h5_state_attribute_value_no_quote(h5_state_t* hs);
static int h5_state_after_attribute_value_quoted_state(h5_state_t* hs);
static int h5_state_comment(h5_state_t* hs);
static int h5_state_cdata(h5_state_t* hs);


/* 12.2.4.44 */
static int h5_state_bogus_comment(h5_state_t* hs);
static int h5_state_bogus_comment2(h5_state_t* hs);

/* 12.2.4.45 */
static int h5_state_markup_declaration_open(h5_state_t* hs);

/* 8.2.4.52 */
static int h5_state_doctype(h5_state_t* hs);

/**
 * public function
 */
void libinjection_h5_init(h5_state_t* hs, const char* s, size_t len, enum html5_flags flags)
{
    memset(hs, 0, sizeof(h5_state_t));
    hs->s = s;
    hs->len = len;

    switch (flags) {
    case DATA_STATE:
        hs->state = h5_state_data;
        break;
    case VALUE_NO_QUOTE:
        hs->state = h5_state_before_attribute_name;
        break;
    case VALUE_SINGLE_QUOTE:
        hs->state = h5_state_attribute_value_single_quote;
        break;
    case VALUE_DOUBLE_QUOTE:
        hs->state = h5_state_attribute_value_double_quote;
        break;
    case VALUE_BACK_QUOTE:
        hs->state = h5_state_attribute_value_back_quote;
        break;
    }
}

/**
 * public function
 */
int libinjection_h5_next(h5_state_t* hs)
{
    assert(hs->state != NULL);
    return (*hs->state)(hs);
}

/**
 * Everything below here is private
 *
 */


static int h5_is_white(char ch)
{
    /*
     * \t = horizontal tab = 0x09
     * \n = newline = 0x0A
     * \v = vertical tab = 0x0B
     * \f = form feed = 0x0C
     * \r = cr  = 0x0D
     */
    return strchr(" \t\n\v\f\r", ch) != NULL;
}

static int h5_skip_white(h5_state_t* hs)
{
    char ch;
    while (hs->pos < hs->len) {
        ch = hs->s[hs->pos];
        switch (ch) {
        case 0x00: /* IE only */
        case 0x20:
        case 0x09:
        case 0x0A:
        case 0x0B: /* IE only */
        case 0x0C:
        case 0x0D: /* IE only */
            hs->pos += 1;
            break;
        default:
            return ch;
        }
    }
    return CHAR_EOF;
}

static int h5_state_eof(h5_state_t* hs)
{
    /* eliminate unused function argument warning */
    (void)hs;
    return 0;
}

static int h5_state_data(h5_state_t* hs)
{
    const char* idx;

    TRACE();
    assert(hs->len >= hs->pos);
    idx = (const char*) memchr(hs->s + hs->pos, CHAR_LT, hs->len - hs->pos);
    if (idx == NULL) {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = hs->len - hs->pos;
        hs->token_type = DATA_TEXT;
        hs->state = h5_state_eof;
        if (hs->token_len == 0) {
            return 0;
        }
    } else {
        hs->token_start = hs->s + hs->pos;
        hs->token_type = DATA_TEXT;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->pos = (size_t)(idx - hs->s) + 1;
        hs->state = h5_state_tag_open;
        if (hs->token_len == 0) {
            return h5_state_tag_open(hs);
        }
    }
    return 1;
}

/**
 * 12 2.4.8
 */
static int h5_state_tag_open(h5_state_t* hs)
{
    char ch;

    TRACE();
    if (hs->pos >= hs->len) {
        return 0;
    }
    ch = hs->s[hs->pos];
    if (ch == CHAR_BANG) {
        hs->pos += 1;
        return h5_state_markup_declaration_open(hs);
    } else if (ch == CHAR_SLASH) {
        hs->pos += 1;
        hs->is_close = 1;
        return h5_state_end_tag_open(hs);
    } else if (ch == CHAR_QUESTION) {
        hs->pos += 1;
        return h5_state_bogus_comment(hs);
    } else if (ch == CHAR_PERCENT) {
        /* this is not in spec.. alternative comment format used
           by IE <= 9 and Safari < 4.0.3 */
        hs->pos += 1;
        return h5_state_bogus_comment2(hs);
    } else if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z')) {
        return h5_state_tag_name(hs);
    } else if (ch == CHAR_NULL) {
        /* IE-ism  NULL characters are ignored */
        return h5_state_tag_name(hs);
    } else {
        /* user input mistake in configuring state */
        if (hs->pos == 0) {
            return h5_state_data(hs);
        }
        hs->token_start = hs->s + hs->pos - 1;
        hs->token_len = 1;
        hs->token_type = DATA_TEXT;
        hs->state = h5_state_data;
        return 1;
    }
}
/**
 * 12.2.4.9
 */
static int h5_state_end_tag_open(h5_state_t* hs)
{
    char ch;

    TRACE();

    if (hs->pos >= hs->len) {
        return 0;
    }
    ch = hs->s[hs->pos];
    if (ch == CHAR_GT) {
        return h5_state_data(hs);
    } else if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z')) {
        return h5_state_tag_name(hs);
    }

    hs->is_close = 0;
    return h5_state_bogus_comment(hs);
}
/*
 *
 */
static int h5_state_tag_name_close(h5_state_t* hs)
{
    TRACE();
    hs->is_close = 0;
    hs->token_start = hs->s + hs->pos;
    hs->token_len = 1;
    hs->token_type = TAG_NAME_CLOSE;
    hs->pos += 1;
    if (hs->pos < hs->len) {
        hs->state = h5_state_data;
    } else {
        hs->state = h5_state_eof;
    }

    return 1;
}

/**
 * 12.2.4.10
 */
static int h5_state_tag_name(h5_state_t* hs)
{
    char ch;
    size_t pos;

    TRACE();
    pos = hs->pos;
    while (pos < hs->len) {
        ch = hs->s[pos];
        if (ch == 0) {
            /* special non-standard case */
            /* allow nulls in tag name   */
            /* some old browsers apparently allow and ignore them */
            pos += 1;
        } else if (h5_is_white(ch)) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len = pos - hs->pos;
            hs->token_type = TAG_NAME_OPEN;
            hs->pos = pos + 1;
            hs->state = h5_state_before_attribute_name;
            return 1;
        } else if (ch == CHAR_SLASH) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len = pos - hs->pos;
            hs->token_type = TAG_NAME_OPEN;
            hs->pos = pos + 1;
            hs->state = h5_state_self_closing_start_tag;
            return 1;
        } else if (ch == CHAR_GT) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len = pos - hs->pos;
            if (hs->is_close) {
                hs->pos = pos + 1;
                hs->is_close = 0;
                hs->token_type = TAG_CLOSE;
                hs->state = h5_state_data;
            } else {
                hs->pos = pos;
                hs->token_type = TAG_NAME_OPEN;
                hs->state = h5_state_tag_name_close;
            }
            return 1;
        } else {
            pos += 1;
        }
    }

    hs->token_start = hs->s + hs->pos;
    hs->token_len = hs->len - hs->pos;
    hs->token_type = TAG_NAME_OPEN;
    hs->state = h5_state_eof;
    return 1;
}

/**
 * 12.2.4.34
 */
static int h5_state_before_attribute_name(h5_state_t* hs)
{
    int ch;

    TRACE();
    ch = h5_skip_white(hs);
    switch (ch) {
    case CHAR_EOF: {
        return 0;
    }
    case CHAR_SLASH: {
        hs->pos += 1;
        return h5_state_self_closing_start_tag(hs);
    }
    case CHAR_GT: {
        hs->state = h5_state_data;
        hs->token_start = hs->s + hs->pos;
        hs->token_len = 1;
        hs->token_type = TAG_NAME_CLOSE;
        hs->pos += 1;
        return 1;
    }
    default: {
        return h5_state_attribute_name(hs);
    }
    }
}

static int h5_state_attribute_name(h5_state_t* hs)
{
    char ch;
    size_t pos;

    TRACE();
    pos = hs->pos + 1;
    while (pos < hs->len) {
        ch = hs->s[pos];
        if (h5_is_white(ch)) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len   = pos - hs->pos;
            hs->token_type  = ATTR_NAME;
            hs->state = h5_state_after_attribute_name;
            hs->pos = pos + 1;
            return 1;
        } else if (ch == CHAR_SLASH) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len   = pos - hs->pos;
            hs->token_type  = ATTR_NAME;
            hs->state = h5_state_self_closing_start_tag;
            hs->pos = pos + 1;
            return 1;
        } else if (ch == CHAR_EQUALS) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len   = pos - hs->pos;
            hs->token_type  = ATTR_NAME;
            hs->state = h5_state_before_attribute_value;
            hs->pos = pos + 1;
            return 1;
        } else if (ch == CHAR_GT) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len   = pos - hs->pos;
            hs->token_type  = ATTR_NAME;
            hs->state = h5_state_tag_name_close;
            hs->pos = pos;
            return 1;
        } else {
            pos += 1;
        }
    }
    /* EOF */
    hs->token_start = hs->s + hs->pos;
    hs->token_len   = hs->len - hs->pos;
    hs->token_type  = ATTR_NAME;
    hs->state = h5_state_eof;
    hs->pos = hs->len;
    return 1;
}

/**
 * 12.2.4.36
 */
static int h5_state_after_attribute_name(h5_state_t* hs)
{
    int c;

    TRACE();
    c = h5_skip_white(hs);
    switch (c) {
    case CHAR_EOF: {
        return 0;
    }
    case CHAR_SLASH: {
        hs->pos += 1;
        return h5_state_self_closing_start_tag(hs);
    }
    case CHAR_EQUALS: {
        hs->pos += 1;
        return h5_state_before_attribute_value(hs);
    }
    case CHAR_GT: {
        return h5_state_tag_name_close(hs);
    }
    default: {
        return h5_state_attribute_name(hs);
    }
    }
}

/**
 * 12.2.4.37
 */
static int h5_state_before_attribute_value(h5_state_t* hs)
{
    int c;
    TRACE();

    c = h5_skip_white(hs);

    if (c == CHAR_EOF) {
        hs->state = h5_state_eof;
        return 0;
    }

    if (c == CHAR_DOUBLE) {
        return h5_state_attribute_value_double_quote(hs);
    } else if (c == CHAR_SINGLE) {
        return h5_state_attribute_value_single_quote(hs);
    } else if (c == CHAR_TICK) {
        /* NON STANDARD IE */
        return h5_state_attribute_value_back_quote(hs);
    } else {
        return h5_state_attribute_value_no_quote(hs);
    }
}


static int h5_state_attribute_value_quote(h5_state_t* hs, char qchar)
{
    const char* idx;

    TRACE();

    /* skip initial quote in normal case.
     * don't do this "if (pos == 0)" since it means we have started
     * in a non-data state.  given an input of '><foo
     * we want to make 0-length attribute name
     */
    if (hs->pos > 0) {
        hs->pos += 1;
    }


    idx = (const char*) memchr(hs->s + hs->pos, qchar, hs->len - hs->pos);
    if (idx == NULL) {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = hs->len - hs->pos;
        hs->token_type = ATTR_VALUE;
        hs->state = h5_state_eof;
    } else {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->token_type = ATTR_VALUE;
        hs->state = h5_state_after_attribute_value_quoted_state;
        hs->pos += hs->token_len + 1;
    }
    return 1;
}

static
int h5_state_attribute_value_double_quote(h5_state_t* hs)
{
    TRACE();
    return h5_state_attribute_value_quote(hs, CHAR_DOUBLE);
}

static
int h5_state_attribute_value_single_quote(h5_state_t* hs)
{
    TRACE();
    return h5_state_attribute_value_quote(hs, CHAR_SINGLE);
}

static
int h5_state_attribute_value_back_quote(h5_state_t* hs)
{
    TRACE();
    return h5_state_attribute_value_quote(hs, CHAR_TICK);
}

static int h5_state_attribute_value_no_quote(h5_state_t* hs)
{
    char ch;
    size_t pos;

    TRACE();
    pos = hs->pos;
    while (pos < hs->len) {
        ch = hs->s[pos];
        if (h5_is_white(ch)) {
            hs->token_type = ATTR_VALUE;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = pos - hs->pos;
            hs->pos = pos + 1;
            hs->state = h5_state_before_attribute_name;
            return 1;
        } else if (ch == CHAR_GT) {
            hs->token_type = ATTR_VALUE;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = pos - hs->pos;
            hs->pos = pos;
            hs->state = h5_state_tag_name_close;
            return 1;
        }
        pos += 1;
    }
    TRACE();
    /* EOF */
    hs->state = h5_state_eof;
    hs->token_start = hs->s + hs->pos;
    hs->token_len = hs->len - hs->pos;
    hs->token_type = ATTR_VALUE;
    return 1;
}

/**
 * 12.2.4.41
 */
static int h5_state_after_attribute_value_quoted_state(h5_state_t* hs)
{
    char ch;

    TRACE();
    if (hs->pos >= hs->len) {
        return 0;
    }
    ch = hs->s[hs->pos];
    if (h5_is_white(ch)) {
        hs->pos += 1;
        return h5_state_before_attribute_name(hs);
    } else if (ch == CHAR_SLASH) {
        hs->pos += 1;
        return h5_state_self_closing_start_tag(hs);
    } else if (ch == CHAR_GT) {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = 1;
        hs->token_type = TAG_NAME_CLOSE;
        hs->pos += 1;
        hs->state = h5_state_data;
        return 1;
    } else {
        return h5_state_before_attribute_name(hs);
    }
}

/**
 * 12.2.4.43
 */
static int h5_state_self_closing_start_tag(h5_state_t* hs)
{
    char ch;

    TRACE();
    if (hs->pos >= hs->len) {
        return 0;
    }
    ch = hs->s[hs->pos];
    if (ch == CHAR_GT) {
        assert(hs->pos > 0);
        hs->token_start = hs->s + hs->pos -1;
        hs->token_len = 2;
        hs->token_type = TAG_NAME_SELFCLOSE;
        hs->state = h5_state_data;
        hs->pos += 1;
        return 1;
    } else {
        return h5_state_before_attribute_name(hs);
    }
}

/**
 * 12.2.4.44
 */
static int h5_state_bogus_comment(h5_state_t* hs)
{
    const char* idx;

    TRACE();
    idx = (const char*) memchr(hs->s + hs->pos, CHAR_GT, hs->len - hs->pos);
    if (idx == NULL) {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = hs->len - hs->pos;
        hs->pos = hs->len;
        hs->state = h5_state_eof;
    } else {
        hs->token_start = hs->s + hs->pos;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->pos =  (size_t)(idx - hs->s) + 1;
        hs->state = h5_state_data;
    }

    hs->token_type = TAG_COMMENT;
    return 1;
}

/**
 * 12.2.4.44 ALT
 */
static int h5_state_bogus_comment2(h5_state_t* hs)
{
    const char* idx;
    size_t pos;

    TRACE();
    pos = hs->pos;
    while (1) {
        idx = (const char*) memchr(hs->s + pos, CHAR_PERCENT, hs->len - pos);
        if (idx == NULL || (idx + 1 >= hs->s + hs->len)) {
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->pos = hs->len;
            hs->token_type = TAG_COMMENT;
            hs->state = h5_state_eof;
            return 1;
        }

        if (*(idx +1) != CHAR_GT) {
            pos = (size_t)(idx - hs->s) + 1;
            continue;
        }

        /* ends in %> */
        hs->token_start = hs->s + hs->pos;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->pos = (size_t)(idx - hs->s) + 2;
        hs->state = h5_state_data;
        hs->token_type = TAG_COMMENT;
        return 1;
    }
}

/**
 * 8.2.4.45
 */
static int h5_state_markup_declaration_open(h5_state_t* hs)
{
    size_t remaining;

    TRACE();
    remaining = hs->len - hs->pos;
    if (remaining >= 7 &&
        /* case insensitive */
        (hs->s[hs->pos + 0] == 'D' || hs->s[hs->pos + 0] == 'd') &&
        (hs->s[hs->pos + 1] == 'O' || hs->s[hs->pos + 1] == 'o') &&
        (hs->s[hs->pos + 2] == 'C' || hs->s[hs->pos + 2] == 'c') &&
        (hs->s[hs->pos + 3] == 'T' || hs->s[hs->pos + 3] == 't') &&
        (hs->s[hs->pos + 4] == 'Y' || hs->s[hs->pos + 4] == 'y') &&
        (hs->s[hs->pos + 5] == 'P' || hs->s[hs->pos + 5] == 'p') &&
        (hs->s[hs->pos + 6] == 'E' || hs->s[hs->pos + 6] == 'e')
        ) {
        return h5_state_doctype(hs);
    } else if (remaining >= 7 &&
               /* upper case required */
               hs->s[hs->pos + 0] == '[' &&
               hs->s[hs->pos + 1] == 'C' &&
               hs->s[hs->pos + 2] == 'D' &&
               hs->s[hs->pos + 3] == 'A' &&
               hs->s[hs->pos + 4] == 'T' &&
               hs->s[hs->pos + 5] == 'A' &&
               hs->s[hs->pos + 6] == '['
        ) {
        hs->pos += 7;
        return h5_state_cdata(hs);
    } else if (remaining >= 2 &&
               hs->s[hs->pos + 0] == '-' &&
               hs->s[hs->pos + 1] == '-') {
        hs->pos += 2;
        return h5_state_comment(hs);
    }

    return h5_state_bogus_comment(hs);
}

/**
 * 12.2.4.48
 * 12.2.4.49
 * 12.2.4.50
 * 12.2.4.51
 *   state machine spec is confusing since it can only look
 *   at one character at a time but simply it's comments end by:
 *   1) EOF
 *   2) ending in -->
 *   3) ending in -!>
 */
static int h5_state_comment(h5_state_t* hs)
{
    char ch;
    const char* idx;
    size_t pos;
    size_t offset;
    const char* end = hs->s + hs->len;

    TRACE();
    pos = hs->pos;
    while (1) {

        idx = (const char*) memchr(hs->s + pos, CHAR_DASH, hs->len - pos);

        /* did not find anything or has less than 3 chars left */
        if (idx == NULL || idx > hs->s + hs->len - 3) {
            hs->state = h5_state_eof;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->token_type = TAG_COMMENT;
            return 1;
        }
        offset = 1;

        /* skip all nulls */
        while (idx + offset < end && *(idx + offset) == 0) {
            offset += 1;
        }
        if (idx + offset == end) {
            hs->state = h5_state_eof;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->token_type = TAG_COMMENT;
            return 1;
        }

        ch = *(idx + offset);
        if (ch != CHAR_DASH && ch != CHAR_BANG) {
            pos = (size_t)(idx - hs->s) + 1;
            continue;
        }

        /* need to test */
#if 0
        /* skip all nulls */
        while (idx + offset < end && *(idx + offset) == 0) {
            offset += 1;
        }
        if (idx + offset == end) {
            hs->state = h5_state_eof;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->token_type = TAG_COMMENT;
            return 1;
        }
#endif

        offset += 1;
        if (idx + offset == end) {
            hs->state = h5_state_eof;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->token_type = TAG_COMMENT;
            return 1;
        }


        ch = *(idx + offset);
        if (ch != CHAR_GT) {
            pos = (size_t)(idx - hs->s) + 1;
            continue;
        }
        offset += 1;

        /* ends in --> or -!> */
        hs->token_start = hs->s + hs->pos;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->pos = (size_t)(idx + offset - hs->s);
        hs->state = h5_state_data;
        hs->token_type = TAG_COMMENT;
        return 1;
    }
}

static int h5_state_cdata(h5_state_t* hs)
{
    const char* idx;
    size_t pos;

    TRACE();
    pos = hs->pos;
    while (1) {
        idx = (const char*) memchr(hs->s + pos, CHAR_RIGHTB, hs->len - pos);

        /* did not find anything or has less than 3 chars left */
        if (idx == NULL || idx > hs->s + hs->len - 3) {
            hs->state = h5_state_eof;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = hs->len - hs->pos;
            hs->token_type = DATA_TEXT;
            return 1;
        } else if ( *(idx+1) == CHAR_RIGHTB && *(idx+2) == CHAR_GT) {
            hs->state = h5_state_data;
            hs->token_start = hs->s + hs->pos;
            hs->token_len = (size_t)(idx - hs->s) - hs->pos;
            hs->pos = (size_t)(idx - hs->s) + 3;
            hs->token_type = DATA_TEXT;
            return 1;
        } else {
            pos = (size_t)(idx - hs->s) + 1;
        }
    }
}

/**
 * 8.2.4.52
 * http://www.w3.org/html/wg/drafts/html/master/syntax.html#doctype-state
 */
static int h5_state_doctype(h5_state_t* hs)
{
    const char* idx;

    TRACE();
    hs->token_start = hs->s + hs->pos;
    hs->token_type = DOCTYPE;

    idx = (const char*) memchr(hs->s + hs->pos, CHAR_GT, hs->len - hs->pos);
    if (idx == NULL) {
        hs->state = h5_state_eof;
        hs->token_len = hs->len - hs->pos;
    } else {
        hs->state = h5_state_data;
        hs->token_len = (size_t)(idx - hs->s) - hs->pos;
        hs->pos = (size_t)(idx - hs->s) + 1;
    }
    return 1;
}
