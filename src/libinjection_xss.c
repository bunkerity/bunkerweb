
#include "libinjection_xss.h"
#include "libinjection.h"
#include "libinjection_html5.h"

#include <assert.h>
#include <stdio.h>

typedef enum attribute {
    TYPE_NONE,
    TYPE_BLACK /* ban always */
    ,
    TYPE_ATTR_URL /* attribute value takes a URL-like object */
    ,
    TYPE_STYLE,
    TYPE_ATTR_INDIRECT /* attribute *name* is given in *value* */
} attribute_t;

static attribute_t is_black_attr(const char *s, size_t len);
static int is_black_tag(const char *s, size_t len);
static int is_black_url(const char *s, size_t len);
static int cstrcasecmp_with_null(const char *a, const char *b, size_t n);
static int html_decode_char_at(const char *src, size_t len, size_t *consumed);
static int htmlencode_startswith(const char *a /* prefix */,
                                 const char *b /* src */, size_t n);

typedef struct stringtype {
    const char *name;
    attribute_t atype;
} stringtype_t;

static const int gsHexDecodeMap[256] = {
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 0,   1,   2,   3,   4,   5,   6,   7,   8,   9,   256, 256,
    256, 256, 256, 256, 256, 10,  11,  12,  13,  14,  15,  256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 10,  11,  12,  13,  14,  15,  256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256};

static int html_decode_char_at(const char *src, size_t len, size_t *consumed) {
    int val = 0;
    size_t i;
    int ch;

    if (len == 0 || src == NULL) {
        *consumed = 0;
        return -1;
    }

    *consumed = 1;
    if (*src != '&' || len < 2) {
        return (unsigned char)(*src);
    }

    if (*(src + 1) != '#') {
        /* normally this would be for named entities
         * but for this case we don't actually care
         */
        return '&';
    }

    if (*(src + 2) == 'x' || *(src + 2) == 'X') {
        ch = (unsigned char)(*(src + 3));
        ch = gsHexDecodeMap[ch];
        if (ch == 256) {
            /* degenerate case  '&#[?]' */
            return '&';
        }
        val = ch;
        i = 4;
        while (i < len) {
            ch = (unsigned char)src[i];
            if (ch == ';') {
                *consumed = i + 1;
                return val;
            }
            ch = gsHexDecodeMap[ch];
            if (ch == 256) {
                *consumed = i;
                return val;
            }
            val = (val * 16) + ch;
            if (val > 0x1000FF) {
                return '&';
            }
            ++i;
        }
        *consumed = i;
        return val;
    } else {
        i = 2;
        ch = (unsigned char)src[i];
        if (ch < '0' || ch > '9') {
            return '&';
        }
        val = ch - '0';
        i += 1;
        while (i < len) {
            ch = (unsigned char)src[i];
            if (ch == ';') {
                *consumed = i + 1;
                return val;
            }
            if (ch < '0' || ch > '9') {
                *consumed = i;
                return val;
            }
            val = (val * 10) + (ch - '0');
            if (val > 0x1000FF) {
                return '&';
            }
            ++i;
        }
        *consumed = i;
        return val;
    }
}

/*
 * These were mostly extracted from:
 * https://raw.githubusercontent.com/WebKit/WebKit/main/Source/WebCore/dom/EventNames.h
 *
 * view-source:
 * data:
 * javascript:
 * events:
 */
static stringtype_t BLACKATTREVENT[] = {
    {"ABORT", TYPE_BLACK},
    {"ACTIVATE", TYPE_BLACK},
    {"ACTIVE", TYPE_BLACK},
    {"ADDSOURCEBUFFER", TYPE_BLACK},
    {"ADDSTREAM", TYPE_BLACK},
    {"ADDTRACK", TYPE_BLACK},
    {"AFTERPRINT", TYPE_BLACK},
    {"ANIMATIONCANCEL", TYPE_BLACK},
    {"ANIMATIONEND", TYPE_BLACK},
    {"ANIMATIONITERATION", TYPE_BLACK},
    {"ANIMATIONSTART", TYPE_BLACK},
    {"AUDIOEND", TYPE_BLACK},
    {"AUDIOPROCESS", TYPE_BLACK},
    {"AUDIOSTART", TYPE_BLACK},
    {"AUTOCOMPLETEERROR", TYPE_BLACK},
    {"AUTOCOMPLETE", TYPE_BLACK},
    {"BEFOREACTIVATE", TYPE_BLACK},
    {"BEFORECOPY", TYPE_BLACK},
    {"BEFORECUT", TYPE_BLACK},
    {"BEFOREINPUT", TYPE_BLACK},
    {"BEFORELOAD", TYPE_BLACK},
    {"BEFOREPASTE", TYPE_BLACK},
    {"BEFOREPRINT", TYPE_BLACK},
    {"BEFOREUNLOAD", TYPE_BLACK},
    {"BEGINEVENT", TYPE_BLACK},
    {"BLOCKED", TYPE_BLACK},
    {"BLUR", TYPE_BLACK},
    {"BOUNDARY", TYPE_BLACK},
    {"BUFFEREDAMOUNTLOW", TYPE_BLACK},
    {"CACHED", TYPE_BLACK},
    {"CANCEL", TYPE_BLACK},
    {"CANPLAYTHROUGH", TYPE_BLACK},
    {"CANPLAY", TYPE_BLACK},
    {"CHANGE", TYPE_BLACK},
    {"CHARGINGCHANGE", TYPE_BLACK},
    {"CHARGINGTIMECHANGE", TYPE_BLACK},
    {"CHECKING", TYPE_BLACK},
    {"CLICK", TYPE_BLACK},
    {"CLOSE", TYPE_BLACK},
    {"COMPLETE", TYPE_BLACK},
    {"COMPOSITIONEND", TYPE_BLACK},
    {"COMPOSITIONSTART", TYPE_BLACK},
    {"COMPOSITIONUPDATE", TYPE_BLACK},
    {"CONNECTING", TYPE_BLACK},
    {"CONNECTIONSTATECHANGE", TYPE_BLACK},
    {"CONNECT", TYPE_BLACK},
    {"CONTEXTMENU", TYPE_BLACK},
    {"CONTROLLERCHANGE", TYPE_BLACK},
    {"COPY", TYPE_BLACK},
    {"CUECHANGE", TYPE_BLACK},
    {"CUT", TYPE_BLACK},
    {"DATAAVAILABLE", TYPE_BLACK},
    {"DATACHANNEL", TYPE_BLACK},
    {"DBLCLICK", TYPE_BLACK},
    {"DEVICECHANGE", TYPE_BLACK},
    {"DEVICEMOTION", TYPE_BLACK},
    {"DEVICEORIENTATION", TYPE_BLACK},
    {"DISCHARGINGTIMECHANGE", TYPE_BLACK},
    {"DISCONNECT", TYPE_BLACK},
    {"DOMACTIVATE", TYPE_BLACK},
    {"DOMCHARACTERDATAMODIFIED", TYPE_BLACK},
    {"DOMCONTENTLOADED", TYPE_BLACK},
    {"DOMFOCUSIN", TYPE_BLACK},
    {"DOMFOCUSOUT", TYPE_BLACK},
    {"DOMNODEINSERTEDINTODOCUMENT", TYPE_BLACK},
    {"DOMNODEINSERTED", TYPE_BLACK},
    {"DOMNODEREMOVEDFROMDOCUMENT", TYPE_BLACK},
    {"DOMNODEREMOVED", TYPE_BLACK},
    {"DOMSUBTREEMODIFIED", TYPE_BLACK},
    {"DOWNLOADING", TYPE_BLACK},
    {"DRAGEND", TYPE_BLACK},
    {"DRAGENTER", TYPE_BLACK},
    {"DRAGLEAVE", TYPE_BLACK},
    {"DRAGOVER", TYPE_BLACK},
    {"DRAGSTART", TYPE_BLACK},
    {"DRAG", TYPE_BLACK},
    {"DROP", TYPE_BLACK},
    {"DURATIONCHANGE", TYPE_BLACK},
    {"EMPTIED", TYPE_BLACK},
    {"ENCRYPTED", TYPE_BLACK},
    {"ENDED", TYPE_BLACK},
    {"ENDEVENT", TYPE_BLACK},
    {"END", TYPE_BLACK},
    {"ENTERPICTUREINPICTURE", TYPE_BLACK},
    {"ENTER", TYPE_BLACK},
    {"ERROR", TYPE_BLACK},
    {"EXIT", TYPE_BLACK},
    {"FETCH", TYPE_BLACK},
    {"FINISH", TYPE_BLACK},
    {"FOCUSIN", TYPE_BLACK},
    {"FOCUSOUT", TYPE_BLACK},
    {"FOCUS", TYPE_BLACK},
    {"FORMCHANGE", TYPE_BLACK},
    {"FORMINPUT", TYPE_BLACK},
    {"GAMEPADCONNECTED", TYPE_BLACK},
    {"GAMEPADDISCONNECTED", TYPE_BLACK},
    {"GESTURECHANGE", TYPE_BLACK},
    {"GESTUREEND", TYPE_BLACK},
    {"GESTURESCROLLEND", TYPE_BLACK},
    {"GESTURESCROLLSTART", TYPE_BLACK},
    {"GESTURESCROLLUPDATE", TYPE_BLACK},
    {"GESTURESTART", TYPE_BLACK},
    {"GESTURETAPDOWN", TYPE_BLACK},
    {"GESTURETAP", TYPE_BLACK},
    {"GOTPOINTERCAPTURE", TYPE_BLACK},
    {"HASHCHANGE", TYPE_BLACK},
    {"ICECANDIDATEERROR", TYPE_BLACK},
    {"ICECANDIDATE", TYPE_BLACK},
    {"ICECONNECTIONSTATECHANGE", TYPE_BLACK},
    {"ICEGATHERINGSTATECHANGE", TYPE_BLACK},
    {"INACTIVE", TYPE_BLACK},
    {"INPUTSOURCESCHANGE", TYPE_BLACK},
    {"INPUT", TYPE_BLACK},
    {"INSTALL", TYPE_BLACK},
    {"INVALID", TYPE_BLACK},
    {"KEYDOWN", TYPE_BLACK},
    {"KEYPRESS", TYPE_BLACK},
    {"KEYSTATUSESCHANGE", TYPE_BLACK},
    {"KEYUP", TYPE_BLACK},
    {"LANGUAGECHANGE", TYPE_BLACK},
    {"LEAVEPICTUREINPICTURE", TYPE_BLACK},
    {"LEVELCHANGE", TYPE_BLACK},
    {"LOADEDDATA", TYPE_BLACK},
    {"LOADEDMETADATA", TYPE_BLACK},
    {"LOADEND", TYPE_BLACK},
    {"LOADINGDONE", TYPE_BLACK},
    {"LOADINGERROR", TYPE_BLACK},
    {"LOADING", TYPE_BLACK},
    {"LOADSTART", TYPE_BLACK},
    {"LOAD", TYPE_BLACK},
    {"LOSTPOINTERCAPTURE", TYPE_BLACK},
    {"MARK", TYPE_BLACK},
    {"MERCHANTVALIDATION", TYPE_BLACK},
    {"MESSAGEERROR", TYPE_BLACK},
    {"MESSAGE", TYPE_BLACK},
    {"MOUSEDOWN", TYPE_BLACK},
    {"MOUSEENTER", TYPE_BLACK},
    {"MOUSELEAVE", TYPE_BLACK},
    {"MOUSEMOVE", TYPE_BLACK},
    {"MOUSEOUT", TYPE_BLACK},
    {"MOUSEOVER", TYPE_BLACK},
    {"MOUSEUP", TYPE_BLACK},
    {"MOUSEWHEEL", TYPE_BLACK},
    {"MUTE", TYPE_BLACK},
    {"NEGOTIATIONNEEDED", TYPE_BLACK},
    {"NEXTTRACK", TYPE_BLACK},
    {"NOMATCH", TYPE_BLACK},
    {"NOUPDATE", TYPE_BLACK},
    {"OBSOLETE", TYPE_BLACK},
    {"OFFLINE", TYPE_BLACK},
    {"ONLINE", TYPE_BLACK},
    {"OPEN", TYPE_BLACK},
    {"ORIENTATIONCHANGE", TYPE_BLACK},
    {"OVERCONSTRAINED", TYPE_BLACK},
    {"OVERFLOWCHANGED", TYPE_BLACK},
    {"PAGEHIDE", TYPE_BLACK},
    {"PAGESHOW", TYPE_BLACK},
    {"PASTE", TYPE_BLACK},
    {"PAUSE", TYPE_BLACK},
    {"PAYERDETAILCHANGE", TYPE_BLACK},
    {"PAYMENTAUTHORIZED", TYPE_BLACK},
    {"PAYMENTMETHODCHANGE", TYPE_BLACK},
    {"PAYMENTMETHODSELECTED", TYPE_BLACK},
    {"PLAYING", TYPE_BLACK},
    {"PLAY", TYPE_BLACK},
    {"POINTERCANCEL", TYPE_BLACK},
    {"POINTERDOWN", TYPE_BLACK},
    {"POINTERENTER", TYPE_BLACK},
    {"POINTERLEAVE", TYPE_BLACK},
    {"POINTERLOCKCHANGE", TYPE_BLACK},
    {"POINTERLOCKERROR", TYPE_BLACK},
    {"POINTERMOVE", TYPE_BLACK},
    {"POINTEROUT", TYPE_BLACK},
    {"POINTEROVER", TYPE_BLACK},
    {"POINTERUP", TYPE_BLACK},
    {"POPSTATE", TYPE_BLACK},
    {"PREVIOUSTRACK", TYPE_BLACK},
    {"PROCESSORERROR", TYPE_BLACK},
    {"PROGRESS", TYPE_BLACK},
    {"PROPERTYCHANGE", TYPE_BLACK},
    {"RATECHANGE", TYPE_BLACK},
    {"READYSTATECHANGE", TYPE_BLACK},
    {"REJECTIONHANDLED", TYPE_BLACK},
    {"REMOVESOURCEBUFFER", TYPE_BLACK},
    {"REMOVESTREAM", TYPE_BLACK},
    {"REMOVETRACK", TYPE_BLACK},
    {"REMOVE", TYPE_BLACK},
    {"RESET", TYPE_BLACK},
    {"RESIZE", TYPE_BLACK},
    {"RESOURCETIMINGBUFFERFULL", TYPE_BLACK},
    {"RESULT", TYPE_BLACK},
    {"RESUME", TYPE_BLACK},
    {"SCROLL", TYPE_BLACK},
    {"SEARCH", TYPE_BLACK},
    {"SECURITYPOLICYVIOLATION", TYPE_BLACK},
    {"SEEKED", TYPE_BLACK},
    {"SEEKING", TYPE_BLACK},
    {"SELECTEND", TYPE_BLACK},
    {"SELECTIONCHANGE", TYPE_BLACK},
    {"SELECTSTART", TYPE_BLACK},
    {"SELECT", TYPE_BLACK},
    {"SHIPPINGADDRESSCHANGE", TYPE_BLACK},
    {"SHIPPINGCONTACTSELECTED", TYPE_BLACK},
    {"SHIPPINGMETHODSELECTED", TYPE_BLACK},
    {"SHIPPINGOPTIONCHANGE", TYPE_BLACK},
    {"SHOW", TYPE_BLACK},
    {"SIGNALINGSTATECHANGE", TYPE_BLACK},
    {"SLOTCHANGE", TYPE_BLACK},
    {"SOUNDEND", TYPE_BLACK},
    {"SOUNDSTART", TYPE_BLACK},
    {"SOURCECLOSE", TYPE_BLACK},
    {"SOURCEENDED", TYPE_BLACK},
    {"SOURCEOPEN", TYPE_BLACK},
    {"SPEECHEND", TYPE_BLACK},
    {"SPEECHSTART", TYPE_BLACK},
    {"SQUEEZEEND", TYPE_BLACK},
    {"SQUEEZESTART", TYPE_BLACK},
    {"SQUEEZE", TYPE_BLACK},
    {"STALLED", TYPE_BLACK},
    {"STARTED", TYPE_BLACK},
    {"START", TYPE_BLACK},
    {"STATECHANGE", TYPE_BLACK},
    {"STOP", TYPE_BLACK},
    {"STORAGE", TYPE_BLACK},
    {"SUBMIT", TYPE_BLACK},
    {"SUCCESS", TYPE_BLACK},
    {"SUSPEND", TYPE_BLACK},
    {"TEXTINPUT", TYPE_BLACK},
    {"TIMEOUT", TYPE_BLACK},
    {"TIMEUPDATE", TYPE_BLACK},
    {"TOGGLE", TYPE_BLACK},
    {"TOGGLE", TYPE_BLACK},
    {"TONECHANGE", TYPE_BLACK},
    {"TOUCHCANCEL", TYPE_BLACK},
    {"TOUCHEND", TYPE_BLACK},
    {"TOUCHFORCECHANGE", TYPE_BLACK},
    {"TOUCHMOVE", TYPE_BLACK},
    {"TOUCHSTART", TYPE_BLACK},
    {"TRACK", TYPE_BLACK},
    {"TRANSITIONCANCEL", TYPE_BLACK},
    {"TRANSITIONEND", TYPE_BLACK},
    {"TRANSITIONRUN", TYPE_BLACK},
    {"TRANSITIONSTART", TYPE_BLACK},
    {"UNCAPTUREDERROR", TYPE_BLACK},
    {"UNHANDLEDREJECTION", TYPE_BLACK},
    {"UNLOAD", TYPE_BLACK},
    {"UNMUTE", TYPE_BLACK},
    {"UPDATEEND", TYPE_BLACK},
    {"UPDATEFOUND", TYPE_BLACK},
    {"UPDATEREADY", TYPE_BLACK},
    {"UPDATESTART", TYPE_BLACK},
    {"UPDATE", TYPE_BLACK},
    {"UPGRADENEEDED", TYPE_BLACK},
    {"VALIDATEMERCHANT", TYPE_BLACK},
    {"VERSIONCHANGE", TYPE_BLACK},
    {"VISIBILITYCHANGE", TYPE_BLACK},
    {"VOLUMECHANGE", TYPE_BLACK},
    {"WAITINGFORKEY", TYPE_BLACK},
    {"WAITING", TYPE_BLACK},
    {"WEBGLCONTEXTCHANGED", TYPE_BLACK},
    {"WEBGLCONTEXTCREATIONERROR", TYPE_BLACK},
    {"WEBGLCONTEXTLOST", TYPE_BLACK},
    {"WEBGLCONTEXTRESTORED", TYPE_BLACK},
    {"WEBKITANIMATIONEND", TYPE_BLACK},
    {"WEBKITANIMATIONITERATION", TYPE_BLACK},
    {"WEBKITANIMATIONSTART", TYPE_BLACK},
    {"WEBKITBEFORETEXTINSERTED", TYPE_BLACK},
    {"WEBKITBEGINFULLSCREEN", TYPE_BLACK},
    {"WEBKITCURRENTPLAYBACKTARGETISWIRELESSCHANGED", TYPE_BLACK},
    {"WEBKITENDFULLSCREEN", TYPE_BLACK},
    {"WEBKITFULLSCREENCHANGE", TYPE_BLACK},
    {"WEBKITFULLSCREENERROR", TYPE_BLACK},
    {"WEBKITKEYADDED", TYPE_BLACK},
    {"WEBKITKEYERROR", TYPE_BLACK},
    {"WEBKITKEYMESSAGE", TYPE_BLACK},
    {"WEBKITMOUSEFORCECHANGED", TYPE_BLACK},
    {"WEBKITMOUSEFORCEDOWN", TYPE_BLACK},
    {"WEBKITMOUSEFORCEUP", TYPE_BLACK},
    {"WEBKITMOUSEFORCEWILLBEGIN", TYPE_BLACK},
    {"WEBKITNEEDKEY", TYPE_BLACK},
    {"WEBKITNETWORKINFOCHANGE", TYPE_BLACK},
    {"WEBKITPLAYBACKTARGETAVAILABILITYCHANGED", TYPE_BLACK},
    {"WEBKITPRESENTATIONMODECHANGED", TYPE_BLACK},
    {"WEBKITREGIONOVERSETCHANGE", TYPE_BLACK},
    {"WEBKITREMOVESOURCEBUFFER", TYPE_BLACK},
    {"WEBKITSOURCECLOSE", TYPE_BLACK},
    {"WEBKITSOURCEENDED", TYPE_BLACK},
    {"WEBKITSOURCEOPEN", TYPE_BLACK},
    {"WEBKITSPEECHCHANGE", TYPE_BLACK},
    {"WEBKITTRANSITIONEND", TYPE_BLACK},
    {"WEBKITWILLREVEALBOTTOM", TYPE_BLACK},
    {"WEBKITWILLREVEALLEFT", TYPE_BLACK},
    {"WEBKITWILLREVEALRIGHT", TYPE_BLACK},
    {"WEBKITWILLREVEALTOP", TYPE_BLACK},
    {"WHEEL", TYPE_BLACK},
    {"WRITEEND", TYPE_BLACK},
    {"WRITESTART", TYPE_BLACK},
    {"WRITE", TYPE_BLACK},
    {"ZOOM", TYPE_BLACK},
    {NULL, TYPE_NONE}};

/*
 * view-source:
 * data:
 * javascript:
 */
static stringtype_t BLACKATTR[] = {
    {"ACTION", TYPE_ATTR_URL} /* form */
    ,
    {"ATTRIBUTENAME",
     TYPE_ATTR_INDIRECT} /* SVG allow indirection of attribute names */
    ,
    {"BY", TYPE_ATTR_URL} /* SVG */
    ,
    {"BACKGROUND", TYPE_ATTR_URL} /* IE6, O11 */
    ,
    {"DATAFORMATAS", TYPE_BLACK} /* IE */
    ,
    {"DATASRC", TYPE_BLACK} /* IE */
    ,
    {"DYNSRC", TYPE_ATTR_URL} /* Obsolete img attribute */
    ,
    {"FILTER", TYPE_STYLE} /* Opera, SVG inline style */
    ,
    {"FORMACTION", TYPE_ATTR_URL} /* HTML 5 */
    ,
    {"FOLDER", TYPE_ATTR_URL} /* Only on A tags, IE-only */
    ,
    {"FROM", TYPE_ATTR_URL} /* SVG */
    ,
    {"HANDLER", TYPE_ATTR_URL} /* SVG Tiny, Opera */
    ,
    {"HREF", TYPE_ATTR_URL},
    {"LOWSRC", TYPE_ATTR_URL} /* Obsolete img attribute */
    ,
    {"POSTER", TYPE_ATTR_URL} /* Opera 10,11 */
    ,
    {"SRC", TYPE_ATTR_URL},
    {"STYLE", TYPE_STYLE},
    {"TO", TYPE_ATTR_URL} /* SVG */
    ,
    {"VALUES", TYPE_ATTR_URL} /* SVG */
    ,
    {"XLINK:HREF", TYPE_ATTR_URL},
    {NULL, TYPE_NONE}};

/* xmlns */
/* `xml-stylesheet` > <eval>, <if expr=> */

/*
  static const char* BLACKATTR[] = {
  "ATTRIBUTENAME",
  "BACKGROUND",
  "DATAFORMATAS",
  "HREF",
  "SCROLL",
  "SRC",
  "STYLE",
  "SRCDOC",
  NULL
  };
*/

static const char *BLACKTAG[] = {
    "APPLET"
    /*    , "AUDIO" */
    ,
    "BASE",
    "COMMENT" /* IE http://html5sec.org/#38 */
    ,
    "EMBED"
    /*   ,  "FORM" */
    ,
    "FRAME",
    "FRAMESET",
    "HANDLER" /* Opera SVG, effectively a script tag */
    ,
    "IFRAME",
    "IMPORT",
    "ISINDEX",
    "LINK",
    "LISTENER"
    /*    , "MARQUEE" */
    ,
    "META",
    "NOSCRIPT",
    "OBJECT",
    "SCRIPT",
    "STYLE"
    /*    , "VIDEO" */
    ,
    "VMLFRAME",
    "XML",
    "XSS",
    NULL};

static int cstrcasecmp_with_null(const char *a, const char *b, size_t n) {
    char ca;
    char cb;
    /* printf("Comparing to %s %.*s\n", a, (int)n, b); */
    while (n-- > 0) {
        cb = *b++;
        if (cb == '\0')
            continue;

        ca = *a++;

        if (cb >= 'a' && cb <= 'z') {
            cb -= 0x20;
        }
        /* printf("Comparing %c vs %c with %d left\n", ca, cb, (int)n); */
        if (ca != cb) {
            return 1;
        }
    }

    if (*a == 0) {
        /* printf(" MATCH \n"); */
        return 0;
    } else {
        return 1;
    }
}

/*
 * Does an HTML encoded  binary string (const char*, length) start with
 * a all uppercase c-string (null terminated), case insensitive!
 *
 * also ignore any embedded nulls in the HTML string!
 *
 * return 1 if match / starts with
 * return 0 if not
 */
static int htmlencode_startswith(const char *a, const char *b, size_t n) {
    size_t consumed;
    int cb;
    int first = 1;
    /* printf("Comparing %s with %.*s\n", a,(int)n,b); */
    while (n > 0) {
        if (*a == 0) {
            /* printf("Match EOL!\n"); */
            return 1;
        }
        cb = html_decode_char_at(b, n, &consumed);
        b += consumed;
        n -= consumed;

        if (first && cb <= 32) {
            /* ignore all leading whitespace and control characters */
            continue;
        }
        first = 0;

        if (cb == 0) {
            /* always ignore null characters in user input */
            continue;
        }

        if (cb == 10) {
            /* always ignore vertical tab characters in user input */
            /* who allows this?? */
            continue;
        }

        if (cb >= 'a' && cb <= 'z') {
            /* upcase */
            cb -= 0x20;
        }

        if (*a != (char)cb) {
            /* printf("    %c != %c\n", *a, cb); */
            /* mismatch */
            return 0;
        }
        a++;
    }

    return (*a == 0) ? 1 : 0;
}

static int is_black_tag(const char *s, size_t len) {
    const char **black;

    if (len < 3) {
        return 0;
    }

    black = BLACKTAG;
    while (*black != NULL) {
        if (cstrcasecmp_with_null(*black, s, len) == 0) {
            /* printf("Got black tag %s\n", *black); */
            return 1;
        }
        black += 1;
    }

    /* anything SVG related */
    if ((s[0] == 's' || s[0] == 'S') && (s[1] == 'v' || s[1] == 'V') &&
        (s[2] == 'g' || s[2] == 'G')) {
        /*        printf("Got SVG tag \n"); */
        return 1;
    }

    /* Anything XSL(t) related */
    if ((s[0] == 'x' || s[0] == 'X') && (s[1] == 's' || s[1] == 'S') &&
        (s[2] == 'l' || s[2] == 'L')) {
        /*      printf("Got XSL tag\n"); */
        return 1;
    }

    return 0;
}

static attribute_t is_black_attr(const char *s, size_t len) {
    stringtype_t *black;

    if (len < 2) {
        return TYPE_NONE;
    }

    if (len >= 5) {

        /* JavaScript on.* event handlers */
        if ((s[0] == 'o' || s[0] == 'O') && (s[1] == 'n' || s[1] == 'N')) {
            black = BLACKATTREVENT;
            const char *s_without_on =
                &s[2]; // start comparing from the third char
            while (black->name != NULL) {
                if (cstrcasecmp_with_null(black->name, s_without_on,
                                          strlen(black->name)) == 0) {
                    /* printf("Got banned attribute name %s\n", black->name); */
                    return black->atype;
                }
                black += 1;
            }
        }

        /* XMLNS can be used to create arbitrary tags */
        if (cstrcasecmp_with_null("XMLNS", s, 5) == 0 ||
            cstrcasecmp_with_null("XLINK", s, 5) == 0) {
            /*      printf("Got XMLNS and XLINK tags\n"); */
            return TYPE_BLACK;
        }
    }

    black = BLACKATTR;
    while (black->name != NULL) {
        if (cstrcasecmp_with_null(black->name, s, len) == 0) {
            /*      printf("Got banned attribute name %s\n", black->name); */
            return black->atype;
        }
        black += 1;
    }

    return TYPE_NONE;
}

static int is_black_url(const char *s, size_t len) {

    static const char *data_url = "DATA";
    static const char *viewsource_url = "VIEW-SOURCE";

    /* obsolete but interesting signal */
    static const char *vbscript_url = "VBSCRIPT";

    /* covers JAVA, JAVASCRIPT, + colon */
    static const char *javascript_url = "JAVA";

    /* skip whitespace */
    while (len > 0 && (*s <= 32 || *s >= 127)) {
        /*
         * HEY: this is a signed character.
         *  We are intentionally skipping high-bit characters too
         *  since they are not ASCII, and Opera sometimes uses UTF-8 whitespace.
         *
         * Also in EUC-JP some of the high bytes are just ignored.
         */
        ++s;
        --len;
    }

    if (htmlencode_startswith(data_url, s, len)) {
        return 1;
    }

    if (htmlencode_startswith(viewsource_url, s, len)) {
        return 1;
    }

    if (htmlencode_startswith(javascript_url, s, len)) {
        return 1;
    }

    if (htmlencode_startswith(vbscript_url, s, len)) {
        return 1;
    }
    return 0;
}

int libinjection_is_xss(const char *s, size_t len, int flags) {
    h5_state_t h5;
    attribute_t attr = TYPE_NONE;

    libinjection_h5_init(&h5, s, len, (enum html5_flags)flags);
    while (libinjection_h5_next(&h5)) {
        if (h5.token_type != ATTR_VALUE) {
            attr = TYPE_NONE;
        }

        if (h5.token_type == DOCTYPE) {
            return 1;
        } else if (h5.token_type == TAG_NAME_OPEN) {
            if (is_black_tag(h5.token_start, h5.token_len)) {
                return 1;
            }
        } else if (h5.token_type == ATTR_NAME) {
            attr = is_black_attr(h5.token_start, h5.token_len);
        } else if (h5.token_type == ATTR_VALUE) {
            /*
             * IE6,7,8 parsing works a bit differently so
             * a whole <script> or other black tag might be hiding
             * inside an attribute value under HTML 5 parsing
             * See http://html5sec.org/#102
             * to avoid doing a full reparse of the value, just
             * look for "<".  This probably need adjusting to
             * handle escaped characters
             */
            /*
              if (memchr(h5.token_start, '<', h5.token_len) != NULL) {
              return 1;
              }
            */

            switch (attr) {
            case TYPE_NONE:
                break;
            case TYPE_BLACK:
                return 1;
            case TYPE_ATTR_URL:
                if (is_black_url(h5.token_start, h5.token_len)) {
                    return 1;
                }
                break;
            case TYPE_STYLE:
                return 1;
            case TYPE_ATTR_INDIRECT:
                /* an attribute name is specified in a _value_ */
                if (is_black_attr(h5.token_start, h5.token_len)) {
                    return 1;
                }
                break;
                /*
                  default:
                  assert(0);
                */
            }
            attr = TYPE_NONE;
        } else if (h5.token_type == TAG_COMMENT) {
            /* IE uses a "`" as a tag ending char */
            if (memchr(h5.token_start, '`', h5.token_len) != NULL) {
                return 1;
            }

            /* IE conditional comment */
            if (h5.token_len > 3) {
                if (h5.token_start[0] == '[' &&
                    (h5.token_start[1] == 'i' || h5.token_start[1] == 'I') &&
                    (h5.token_start[2] == 'f' || h5.token_start[2] == 'F')) {
                    return 1;
                }
                if ((h5.token_start[0] == 'x' || h5.token_start[0] == 'X') &&
                    (h5.token_start[1] == 'm' || h5.token_start[1] == 'M') &&
                    (h5.token_start[2] == 'l' || h5.token_start[2] == 'L')) {
                    return 1;
                }
            }

            if (h5.token_len > 5) {
                /*  IE <?import pseudo-tag */
                if (cstrcasecmp_with_null("IMPORT", h5.token_start, 6) == 0) {
                    return 1;
                }

                /*  XML Entity definition */
                if (cstrcasecmp_with_null("ENTITY", h5.token_start, 6) == 0) {
                    return 1;
                }
            }
        }
    }
    return 0;
}

/*
 * wrapper
 *
 *
 * const char* s: input string, may contain nulls, does not need to be
 * null-terminated. size_t len: input string length.
 *
 * Further info:
 *   - https://github.com/client9/libinjection/issues/150
 *   - https://github.com/libinjection/libinjection/issues/44
 *
 */
int libinjection_xss(const char *s, size_t slen) {
    if (libinjection_is_xss(s, slen, DATA_STATE)) {
        return 1;
    }
    if (libinjection_is_xss(s, slen, VALUE_NO_QUOTE)) {
        return 1;
    }
    if (libinjection_is_xss(s, slen, VALUE_SINGLE_QUOTE)) {
        return 1;
    }
    if (libinjection_is_xss(s, slen, VALUE_DOUBLE_QUOTE)) {
        return 1;
    }
    if (libinjection_is_xss(s, slen, VALUE_BACK_QUOTE)) {
        return 1;
    }

    return 0;
}
