/*
 * luagd -- GD bindings for Lua.
 * (c) 2004-13 Alexandre Erwin Ittner <alexandre@ittner.com.br>
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDER BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * If you use this package in a product, an acknowledgment in the product
 * documentation would be greatly appreciated (but it is not required).
 *
 */
 
#include <lua.h>
#include <lauxlib.h>
#include <stdlib.h>

#include <gd.h>

/* Standard gd fonts */
#include <gdfonts.h>
#include <gdfontl.h>
#include <gdfontmb.h>
#include <gdfontg.h>
#include <gdfontt.h>

#ifndef VERSION
 #error "Trying to build without -DVERSION=xxx defined. Check the Makefile"
#endif
#define LIB_VERSION     "lua-gd " VERSION
#define LIB_COPYRIGHT   LIB_VERSION " (c) 2004-13 Alexandre Erwin Ittner"

#define GD_IMAGE_PTR_TYPENAME   "gdImagePtr_handle"


/* Compatibility between Lua 5.1 and Lua 5.2 */
#if LUA_VERSION_NUM < 501
 #error "Unsuported Lua version. You must use Lua >= 5.1"
#endif

#if LUA_VERSION_NUM < 502
 #define luaL_setfuncs(L, f, unused)  { luaL_register(L, NULL, f); }
 #define lua_rawlen lua_objlen
#endif

#define boxptr(L, p)   (*(void**)(lua_newuserdata(L, sizeof(void*))) = (p))
#define unboxptr(L, i) (*(void**)(lua_touserdata(L, i)))

/* Table assumed on top */
#define tblseticons(L, c, v)    \
    lua_pushliteral(L, c);      \
    lua_pushnumber(L, v);       \
    lua_settable(L, -3);

/* Standard gd fonts */
#define MY_GD_FONT_SMALL            0
#define MY_GD_FONT_LARGE            1
#define MY_GD_FONT_MEDIUM_BOLD      2
#define MY_GD_FONT_GIANT            3
#define MY_GD_FONT_TINY             4


static int typerror(lua_State *L, int narg, const char *tname) {
    const char *msg = lua_pushfstring(L, "%s expected, got %s",
        tname, luaL_typename(L, narg));
    return luaL_argerror(L, narg, msg);
}


static gdImagePtr getImagePtr(lua_State *L, int i) {
    if (luaL_checkudata(L, i, GD_IMAGE_PTR_TYPENAME) != NULL) {
        gdImagePtr im = unboxptr(L, i);
        if (im == NULL)
            luaL_error(L, "attempt to use an invalid " GD_IMAGE_PTR_TYPENAME);
        return im;
    }
    typerror(L, i, GD_IMAGE_PTR_TYPENAME);
    return NULL;
}


static void pushImagePtr(lua_State *L, gdImagePtr im) {
    boxptr(L, im);
    luaL_getmetatable(L, GD_IMAGE_PTR_TYPENAME);
    lua_setmetatable(L, -2);    /* Done */
}


static gdFontPtr getStdFont(lua_State *L, int i) {
    int size;

    if (lua_isnumber(L, i) == 0) {
        typerror(L, i, "Standard GD Font");
        return gdFontGetSmall();
    }

    size = luaL_checkinteger(L, i);
    switch(size) {
        case MY_GD_FONT_SMALL:
            return gdFontGetSmall();

        case MY_GD_FONT_LARGE:
            return gdFontGetLarge();

        case MY_GD_FONT_MEDIUM_BOLD:
            return gdFontGetMediumBold();

        case MY_GD_FONT_GIANT:
            return gdFontGetGiant();

        case MY_GD_FONT_TINY:
            return gdFontGetTiny();

        default:
            typerror(L, i, "Standard GD Font");
            return gdFontGetSmall();
    }

    return gdFontGetSmall(); /* Not reached */
}




/* 
 * Reads a Lua table and returns a pointer to a "gdFTStringExtra" struct. The
 * table should have the following fields:
 *
 * {
 *     linespacing = 1.0,                   -- linespacing for '\n'
 *     charmap = gd.FTEX_Unicode,           -- default charset
 *     hdpi = 96,                           -- horizontal resolution
 *     vdpi = 96,                           -- vertical resolution
 *     disable_kerning = true,              -- disable kerning?
 *     xshow = true,                        -- return char positions?
 *     return_font_path_name = true,        -- return font path names?
 *     fontconfig = true                    -- use fontconfig?
 * }
 * 
 */
#ifdef GD_FREETYPE
static gdFTStringExtra *getFTStringExtraPtr(lua_State *L, int i) {
    luaL_checktype(L, i, LUA_TTABLE);

    gdFTStringExtra *ex = (gdFTStringExtra*) malloc(sizeof(gdFTStringExtra));
    if (ex == NULL)
        luaL_error(L, "Memory allocation failure");

    ex->flags = 0;

    lua_pushstring(L, "linespacing");
    lua_gettable(L, i);
    if (!lua_isnil(L, -1)) {
        ex->flags |= gdFTEX_LINESPACE;
        ex->linespacing = (double) lua_tonumber(L, -1);
    }
    lua_pop(L, 1);

    lua_pushstring(L, "charmap");
    lua_gettable(L, i);
    if (!lua_isnil(L, -1)) {
        ex->flags |= gdFTEX_CHARMAP;;
        ex->charmap = (int) lua_tonumber(L, -1);
        switch(ex->charmap) {
            case gdFTEX_Unicode:
            case gdFTEX_Shift_JIS:
            case gdFTEX_Big5:
            /* Future charsets here */
                break;
            default:
                free(ex);
                luaL_error(L, "Invalid charset");
        }
    }
    lua_pop(L, 1);

    ex->hdpi = 96;
    ex->vdpi = 96;

    lua_pushstring(L, "hdpi");
    lua_gettable(L, i);
    if (!lua_isnil(L, -1)) {
        ex->flags |= gdFTEX_RESOLUTION;
        ex->hdpi = (double) lua_tonumber(L, -1);
    }
    lua_pop(L, 1);

    lua_pushstring(L, "vdpi");
    lua_gettable(L, i);
    if (!lua_isnil(L, -1)) {
        ex->flags |= gdFTEX_RESOLUTION;
        ex->vdpi = (double) lua_tonumber(L, -1);
    }
    lua_pop(L, 1);

    lua_pushstring(L, "disable_kerning");
    lua_gettable(L, i);
    if (lua_toboolean(L, -1))
        ex->flags |= gdFTEX_DISABLE_KERNING;
    lua_pop(L, 1);

    lua_pushvalue(L, i);
    lua_pushstring(L, "xshow");
    lua_gettable(L, i);
    if (lua_toboolean(L, -1))
        ex->flags |= gdFTEX_XSHOW;
    lua_pop(L, 1);

    lua_pushstring(L, "return_font_path_name");
    lua_gettable(L, i);
    if (lua_toboolean(L, -1))
        ex->flags |= gdFTEX_RETURNFONTPATHNAME;
    lua_pop(L, 1);

    lua_pushstring(L, "fontconfig");
    lua_gettable(L, i);
    if (lua_toboolean(L, -1))
        ex->flags |= gdFTEX_FONTCONFIG;
    lua_pop(L, 1);

    return ex;
}
#endif 


/* gdImageCreate(int sx, int sy) */
static int LgdImageCreate(lua_State *L) {
    int sx, sy;
    gdImagePtr im;

    sx = luaL_checkinteger(L, 1);
    sy = luaL_checkinteger(L, 2);
    im = gdImageCreate(sx, sy);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}

/* gdImageCreatePalette(int sx, int sy) */
/* Useless? */
static int LgdImageCreatePalette(lua_State *L) {
    int sx, sy;
    gdImagePtr im;

    sx = luaL_checkinteger(L, 1);
    sy = luaL_checkinteger(L, 2);
    im = gdImageCreatePalette(sx, sy);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}



/* gdImageCreateTrueColor(int sx, int sy) */
static int LgdImageCreateTrueColor(lua_State *L) {
    int sx, sy;
    gdImagePtr im;

    sx = luaL_checkinteger(L, 1);
    sy = luaL_checkinteger(L, 2);
    im = gdImageCreateTrueColor(sx, sy);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}

/* gdImagePtr gdImageCreatePaletteFromTrueColor(gdImagePtr im, int ditherFlag,
    int colorsWanted) */
static int LgdImageCreatePaletteFromTrueColor(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int dither = lua_toboolean(L, 2);
    int colors = luaL_checkinteger(L, 3);
    gdImagePtr nim = gdImageCreatePaletteFromTrueColor(im, dither, colors);
    
    if (nim)
        pushImagePtr(L, nim);
    else
        lua_pushnil(L);
    return 1;
}


/* void gdImageTrueColorToPalette(gdImagePtr im, int ditherFlag,
    int colorsWanted) */
static int LgdImageTrueColorToPalette(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int dither = lua_toboolean(L, 2);
    int colors = luaL_checkinteger(L, 3);

    gdImageTrueColorToPalette(im, dither, colors);
    return 0;
}



/* gdImageDestroy(gdImagePtr im) */
static int LgdImageDestroy(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    if (im)
        gdImageDestroy(im);
    return 0;
}

#ifdef GD_JPEG
/* gdImageCreateFromJpeg(FILE *in) */
/* Changed to: gd.createFromJpeg(char *filename) */
static int LgdImageCreateFromJpeg(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromJpeg(fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromJpegPtr(int size, void *data) */
static int LgdImageCreateFromJpegPtr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromJpegPtr(size, str);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}
#endif


#ifdef GD_GIF
/* gdImageCreateFromGif (FILE *in) */
/* Changed to: gd.createFromGif (filename) */
static int LgdImageCreateFromGif (lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGif (fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}

/* gdImageCreateFromGifPtr(int size, void *data) */
static int LgdImageCreateFromGifPtr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGifPtr(size, str);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}
#endif


#ifdef GD_PNG
/* gdImageCreateFromPng(FILE *in) */
/* Changed to: gd.createFromPng(filename) */
static int LgdImageCreateFromPng(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromPng(fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromPngPtr(int size, void *data) */
static int LgdImageCreateFromPngPtr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromPngPtr(size, str);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}
#endif


/* gdImageCreateFromGd(FILE *in) */
/* Changed to: gd.createFromGd(filename) */
static int LgdImageCreateFromGd(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGd(fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromGdPtr(int size, void *data) */
static int LgdImageCreateFromGdPtr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGdPtr(size, str);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromGd2(FILE *in) */
/* Changed to: gd.createFromGd2(filename) */
static int LgdImageCreateFromGd2(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGd2(fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromGd2Ptr(int size, void *data) */
static int LgdImageCreateFromGd2Ptr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGd2Ptr(size, str);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromGd2Part(FILE *in, int x, int y, int w, int h) */
/* Changed to: gd.createFromGd2Part(filename, x, y, w, h)) */
static int LgdImageCreateFromGd2Part(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);
    const int x = luaL_checkinteger(L, 2);
    const int y = luaL_checkinteger(L, 3);
    const int w = luaL_checkinteger(L, 4);
    const int h = luaL_checkinteger(L, 5);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGd2Part(fp, x, y, w, h);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromGd2PartPtr(int size, void *data,
                int srcX, int srcY, int w, int h)  */
static int LgdImageCreateFromGd2PartPtr(lua_State *L) {
    gdImagePtr im;
    int size = lua_rawlen(L, 1);
    void *str = (void*) luaL_checkstring(L, 1);
    const int x = luaL_checkinteger(L, 2);
    const int y = luaL_checkinteger(L, 3);
    const int w = luaL_checkinteger(L, 4);
    const int h = luaL_checkinteger(L, 5);

    if (str == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromGd2PartPtr(size, str, x, y, w, h);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


#ifdef GD_XPM
/* gdImageCreateFromXbm(FILE *in) */
/* Changed to: gd.createFromXbm(filename) */
static int LgdImageCreateFromXbm(lua_State *L) {
    gdImagePtr im;
    FILE *fp;
    const char *fname = luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    if ((fp = fopen(fname, "rb")) == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromXbm(fp);
    fclose(fp);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}


/* gdImageCreateFromXpm(char *filename) */
static int LgdImageCreateFromXpm(lua_State *L) {
    gdImagePtr im;
    char *fname = (char*) luaL_checkstring(L, 1);

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;  /* Error */
    }
    im = gdImageCreateFromXpm(fname);
    if (im != NULL)
        pushImagePtr(L, im);
    else
        lua_pushnil(L); /* Error */
    return 1;
}
#endif



#ifdef GD_JPEG
/* gdImageJpeg(gdImagePtr im, FILE *out, int quality) */
/* Changed to: gd.jpeg(im, fname, quality) */
static int LgdImageJpeg(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    int quality = luaL_checkinteger(L, 3);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImageJpeg(im, fp, quality);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void *gdImageJpegPtr(gdImagePtr im, int quality) */
static int LgdImageJpegPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int quality = luaL_checkinteger(L, 2);
    char *str;
    int size;

    str = gdImageJpegPtr(im, &size, quality);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}
#endif

#ifdef GD_PNG
/* gdImagePng(gdImagePtr im, FILE *out) */
/* Changed to: gd.png(im, fname) */
static int LgdImagePng(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImagePng(im, fp);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void *gdImagePngPtr(gdImagePtr im) */
static int LgdImagePngPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    char *str;
    int size;

    str = gdImagePngPtr(im, &size);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}


/* gdImagePngEx(gdImagePtr im, FILE *out, int compression_level) */
/* Changed to: gd.pngEx(im, fname, compression_level) */
static int LgdImagePngEx(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    int level = luaL_checkinteger(L, 3);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImagePngEx(im, fp, level);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void *gdImagePngPtrEx(gdImagePtr im, int compression_level) */
static int LgdImagePngPtrEx(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int level = luaL_checkinteger(L, 2);
    char *str;
    int size;

    str = gdImagePngPtrEx(im, &size, level);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}
#endif


#ifdef GD_GIF
/* gdImageGif (gdImagePtr im, FILE *out) */
/* Changed to: gd.gif (im, fname) */
static int LgdImageGif (lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImageGif (im, fp);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}
#endif

#ifdef GD_GIF
/* void *gdImageGifPtr(gdImagePtr im) */
static int LgdImageGifPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    char *str;
    int size;

    str = gdImageGifPtr(im, &size);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}
#endif


/* gdImageGd(gdImagePtr im, FILE *out) */
/* Changed to: gd.gd(im, fname) */
static int LgdImageGd(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImageGd(im, fp);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void *gdImageGdPtr(gdImagePtr im) */
static int LgdImageGdPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    char *str;
    int size;

    str = gdImageGdPtr(im, &size);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}



/* gdImageGd2(gdImagePtr im, FILE *out, int chunkSize, int fmt) */
/* Changed to: gd.gd2(im, fname, chunkSize, fmt) */
static int LgdImageGd2(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    const char *fname = luaL_checkstring(L, 2);
    int cs = luaL_checkinteger(L, 3);
    int fmt = luaL_checkinteger(L, 4);
    FILE *fp;

    if (fname == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0);
        return 1;
    }
    gdImageGd2(im, fp, cs, fmt);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void* gdImageGd2Ptr(gdImagePtr im, int chunkSize, int fmt, int *size) */
static int LgdImageGd2Ptr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int cs = luaL_checkinteger(L, 2);
    int fmt = luaL_checkinteger(L, 3);
    char *str;
    int size;

    str = gdImageGd2Ptr(im, cs, fmt, &size);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else
        lua_pushnil(L);  /* Error */
    return 1;
}


/* void gdImageWBMP(gdImagePtr im, int fg, FILE *out) */
/* Changed to: gd.wbmp(im, int fg, filename) */
static int LgdImageWBMP(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int fg = luaL_checkinteger(L, 2);
    const char *fname = luaL_checkstring(L, 3);
    FILE *fp;

    if (fname == NULL) {
        lua_pushnil(L);
        return 1;
    }
    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushnil(L);
        return 1;
    }
    gdImageWBMP(im, fg, fp);
    fclose(fp);
    lua_pushboolean(L, 1);
    return 1;
}


/* void* gdImageWBMPPtr(gdImagePtr im, int *size) */
static int LgdImageWBMPPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int fg = luaL_checkinteger(L, 2);
    char *str;
    int size;

    str = gdImageWBMPPtr(im, &size, fg);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else {
        lua_pushnil(L);  /* Error */
    }
    return 1;
}


/* int gdImageColorAllocate(gdImagePtr im, int r, int g, int b) */
static int LgdImageColorAllocate(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c;

    c = gdImageColorAllocate(im, r, g, b);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorAllocateAlpha(gdImagePtr im, int r, int g, int b, int a) */
static int LgdImageColorAllocateAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int a = luaL_checkinteger(L, 5);
    int c;

    c = gdImageColorAllocateAlpha(im, r, g, b, a);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorClosest(gdImagePtr im, int r, int g, int b) */
static int LgdImageColorClosest(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c;

    c = gdImageColorClosest(im, r, g, b);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorClosestAlpha(gdImagePtr im, int r, int g, int b, int a) */
static int LgdImageColorClosestAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int a = luaL_checkinteger(L, 5);
    int c;

    c = gdImageColorClosestAlpha(im, r, g, b, a);
    if (c > 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorClosestHWB(gdImagePtr im, int r, int g, int b) */
static int LgdImageColorClosestHWB(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c;

    c = gdImageColorClosestHWB(im, r, g, b);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorExact(gdImagePtr im, int r, int g, int b) */
static int LgdImageColorExact(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c;

    c = gdImageColorExact(im, r, g, b);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorExactAlpha(gdImagePtr im, int r, int g, int b, int a) */
static int LgdImageColorExactAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int a = luaL_checkinteger(L, 5);
    int c;

    c = gdImageColorExactAlpha(im, r, g, b, a);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorResolve(gdImagePtr im, int r, int g, int b) */
static int LgdImageColorResolve(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c;

    c = gdImageColorResolve(im, r, g, b);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorResolveAlpha(gdImagePtr im, int r, int g, int b, int a) */
static int LgdImageColorResolveAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);
    int g = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int a = luaL_checkinteger(L, 5);
    int c;

    c = gdImageColorResolveAlpha(im, r, g, b, a);
    if (c >= 0)
        lua_pushnumber(L, c);  /* ok */
    else
        lua_pushnil(L); /* Can not allocate color */
    return 1;
}


/* int gdImageColorsTotal(gdImagePtr im) */
static int LgdImageColorsTotal(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);

    lua_pushnumber(L, gdImageColorsTotal(im));  /* ok */
    return 1;
}


/* int gdImageRed(gdImagePtr im, int c) */
static int LgdImageRed(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);

    lua_pushnumber(L, gdImageRed(im, c));  /* ok */
    return 1;
}

/* int gdImageBlue(gdImagePtr im, int c) */
static int LgdImageBlue(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);

    lua_pushnumber(L, gdImageBlue(im, c));  /* ok */
    return 1;
}

/* int gdImageBlue(gdImagePtr im, int c) */
static int LgdImageGreen(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);

    lua_pushnumber(L, gdImageGreen(im, c));  /* ok */
    return 1;
}

/* int gdImageAlpha(gdImagePtr im, int color) */
static int LgdImageAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);
    lua_pushnumber(L, gdImageAlpha(im, c));
    return 1;
}

/* int gdImageGetInterlaced(gdImagePtr im) */
static int LgdImageGetInterlaced(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int ret = gdImageGetInterlaced(im);

    if (ret != 0)
        lua_pushnumber(L, ret);
    else
        lua_pushnil(L);
    return 1;
}

/* int gdImageGetTransparent(gdImagePtr im) */
static int LgdImageGetTransparent(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int ret = gdImageGetTransparent(im);

    if (ret != -1)
        lua_pushnumber(L, ret);
    else
        lua_pushnil(L);
    return 1;
}


/* void gdImageColorTransparent(gdImagePtr im, int c) */
static int LgdImageColorTransparent(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = -1;
    if (!lua_isnil(L, 2))
      c = luaL_checkinteger(L, 2);
    gdImageColorTransparent(im, c);
    return 0;
}


/* void gdImageColorDeallocate(gdImagePtr im, int c) */
static int LgdImageColorDeallocate(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);
    gdImageColorDeallocate(im, c);
    return 0;
}


/* int gdImageSX(gdImagePtr im) */
static int LgdImageSX(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    lua_pushnumber(L, gdImageSX(im));
    return 1;
}


/* int gdImageSY(gdImagePtr im) */
static int LgdImageSY(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    lua_pushnumber(L, gdImageSY(im));
    return 1;
}


/* Fear the power of the Moon!!  ---   x, y = im:sizeXY() */
static int LgdImageSXY(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    lua_pushnumber(L, gdImageSX(im));
    lua_pushnumber(L, gdImageSY(im));
    return 2;
}


/* int gdImageBoundsSafe(gdImagePtr im, int x, int y) */
static int LgdImageBoundsSafe(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x = luaL_checkinteger(L, 2);
    int y = luaL_checkinteger(L, 3);

    if (gdImageBoundsSafe(im, x, y) != 0)
        lua_pushboolean(L, 1);
    else
        lua_pushboolean(L, 0);
    return 1;
}


/* int gdImageGetPixel(gdImagePtr im, int x, int y) */
static int LgdImageGetPixel(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x = luaL_checkinteger(L, 2);
    int y = luaL_checkinteger(L, 3);

    lua_pushnumber(L, gdImageGetPixel(im, x, y));
    return 1;
}


/* void gdImageSetPixel(gdImagePtr im, int x, int y, int color) */
static int LgdImageSetPixel(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x = luaL_checkinteger(L, 2);
    int y = luaL_checkinteger(L, 3);
    int c = luaL_checkinteger(L, 4);

    gdImageSetPixel(im, x, y, c);
    return 0;
}


/* void gdImageLine(gdImagePtr im, int x1, int y1, int x2, int y2, int c) */
static int LgdImageLine(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x1 = luaL_checkinteger(L, 2);
    int y1 = luaL_checkinteger(L, 3);
    int x2 = luaL_checkinteger(L, 4);
    int y2 = luaL_checkinteger(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageLine(im, x1, y1, x2, y2, c);
    return 0;
}

/* void gdImageRectangle(gdImagePtr im, int x1, int y1, int x2, int y2,
        int c) */
static int LgdImageRectangle(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x1 = luaL_checkinteger(L, 2);
    int y1 = luaL_checkinteger(L, 3);
    int x2 = luaL_checkinteger(L, 4);
    int y2 = luaL_checkinteger(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageRectangle(im, x1, y1, x2, y2, c);
    return 0;
}


/* void gdImageFilledRectangle(gdImagePtr im, int x1, int y1, int x2, int y2,
        int c) */
static int LgdImageFilledRectangle(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x1 = luaL_checkinteger(L, 2);
    int y1 = luaL_checkinteger(L, 3);
    int x2 = luaL_checkinteger(L, 4);
    int y2 = luaL_checkinteger(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageFilledRectangle(im, x1, y1, x2, y2, c);
    return 0;
}


/* Stack must have ONLY the table of points */
static gdPoint *getPointList(lua_State *L, int *size) {
    gdPoint *plist;
    int i;

    luaL_checktype(L, -1, LUA_TTABLE);
    *size = lua_rawlen(L, -1);
    plist = (gdPoint*) malloc(*size * sizeof(gdPoint));

    for (i = 0; i < *size; i++) {
        /* Stack: T */
        lua_rawgeti(L, 1, i + 1);

        /* Stack:  T, T'  */
        if (lua_type(L, 2) != LUA_TTABLE) {
            free(plist);
            typerror(L, 2, "Point");
        }

        lua_rawgeti(L, 2, 1);
        /* Stack:  T, T', X  */
        plist[i].x = luaL_checkinteger(L, -1);
        lua_remove(L, -1);

        lua_rawgeti(L, 2, 2);
        /* Stack:  T, T', Y  */
        plist[i].y = luaL_checkinteger(L, -1);
        lua_remove(L, -1);

        /* Stack:  T, T' */
        lua_remove(L, -1);

        /* Stack: T */
    }

    lua_remove(L, -1);
    return plist;
}



/* void gdImagePolygon(gdImagePtr im, gdPointPtr points, int pointsTotal,
        int color)
  Changed to: gd.polygon(im, { { x1, y1 }, { x2, y2 } ... }, color)  */
static int LgdImagePolygon(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdPoint *plist;
    int size;
    int c;

    c = luaL_checkinteger(L, 3);
    lua_remove(L, 3); /* Get and drop color */
    lua_remove(L, 1); /* Drop image from the stack */
    plist = getPointList(L, &size);
    gdImagePolygon(im, plist, size, c);
    free(plist);
    return 0;
}



/* void gdImageFilledPolygon(gdImagePtr im, gdPointPtr points,
        int pointsTotal, int color)
  Changed to: gd.filledPolygon(im, { { x1, y1 }, { x2, y2 } ... }, color) */
static int LgdImageFilledPolygon(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdPoint *plist;
    int size;
    int c;

    c = luaL_checkinteger(L, 3);
    lua_remove(L, 3); /* Get and drop color */
    lua_remove(L, 1); /* Drop image from the stack */

    plist = getPointList(L, &size);
    gdImageFilledPolygon(im, plist, size, c);
    free(plist);
    return 0;
}


/* void gdImageOpenPolygon(gdImagePtr im, gdPointPtr points,
        int pointsTotal, int color)
  Changed to: gd.openPolygon(im, { { x1, y1 }, { x2, y2 } ... }, color) */
static int LgdImageOpenPolygon(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdPoint *plist;
    int size;
    int c;

    c = luaL_checkinteger(L, 3);
    lua_remove(L, 3); /* Get and drop color */
    lua_remove(L, 1); /* Drop image from the stack */

    plist = getPointList(L, &size);
    gdImageOpenPolygon(im, plist, size, c);
    free(plist);
    return 0;
}



/* void gdImageArc(gdImagePtr im, int cx, int cy, int w, int h, int s, int e,
    int color) */
static int LgdImageArc(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int cx = luaL_checkinteger(L, 2);
    int cy = luaL_checkinteger(L, 3);
    int w = luaL_checkinteger(L, 4);
    int h = luaL_checkinteger(L, 5);
    int s = luaL_checkinteger(L, 6);
    int e = luaL_checkinteger(L, 7);
    int c = luaL_checkinteger(L, 8);

    gdImageArc(im, cx, cy, w, h, s, e, c);
    return 0;
}


/* void gdImageFilledArc(gdImagePtr im, int cx, int cy, int w, int h,
    int s, int e, int color, int style) */
static int LgdImageFilledArc(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int cx = luaL_checkinteger(L, 2);
    int cy = luaL_checkinteger(L, 3);
    int w = luaL_checkinteger(L, 4);
    int h = luaL_checkinteger(L, 5);
    int s = luaL_checkinteger(L, 6);
    int e = luaL_checkinteger(L, 7);
    int c = luaL_checkinteger(L, 8);
    int sty = luaL_checkinteger(L, 9);

    gdImageFilledArc(im, cx, cy, w, h, s, e, c, sty);
    return 0;
}


/* void gdImageFilledEllipse(gdImagePtr im, int cx, int cy, int w, int h,
        int color) */
static int LgdImageFilledEllipse(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int cx = luaL_checkinteger(L, 2);
    int cy = luaL_checkinteger(L, 3);
    int w = luaL_checkinteger(L, 4);
    int h = luaL_checkinteger(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageFilledEllipse(im, cx, cy, w, h, c);
    return 0;
}


/* void gdImageFill(gdImagePtr im, int x, int y, int color) */
static int LgdImageFill(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x = luaL_checkinteger(L, 2);
    int y = luaL_checkinteger(L, 3);
    int c = luaL_checkinteger(L, 4);

    gdImageFill(im, x, y, c);
    return 0;
}


/* void gdImageFillToBorder(gdImagePtr im, int x, int y, int border,
        int color) */
static int LgdImageFillToBorder(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x = luaL_checkinteger(L, 2);
    int y = luaL_checkinteger(L, 3);
    int b = luaL_checkinteger(L, 4);
    int c = luaL_checkinteger(L, 5);

    gdImageFillToBorder(im, x, y, b, c);
    return 0;
}


/* void gdImageSetAntiAliased(gdImagePtr im, int c) */
static int LgdImageSetAntiAliased(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);

    gdImageSetAntiAliased(im, c);
    return 0;
}


/* void gdImageSetAntiAliasedDontBlend(gdImagePtr im, int c) */
static int LgdImageSetAntiAliasedDontBlend(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int c = luaL_checkinteger(L, 2);

    gdImageSetAntiAliasedDontBlend(im, c, 1);
    return 0;
}


/* void gdImageSetBrush(gdImagePtr im, gdImagePtr brush) */
static int LgdImageSetBrush(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdImagePtr b = getImagePtr(L, 2);

    gdImageSetBrush(im, b);
    return 0;
}


/* void gdImageSetTile(gdImagePtr im, gdImagePtr tile) */
static int LgdImageSetTile(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdImagePtr t = getImagePtr(L, 1);

    gdImageSetTile(im, t);
    return 0;
}


/* void gdImageSetStyle(gdImagePtr im, int *style, int styleLength)  */
/* Changed To: gd.setStyle(im, { c1, c2, c3,  ...  } ) */
static int LgdImageSetStyle(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int *slist;
    int size;
    int i;

    /* Stack: Im, T */
    luaL_checktype(L, -1, LUA_TTABLE);
    size = lua_rawlen(L, -1);
    slist = (int*) malloc(size * sizeof(int));

    for (i = 0; i < size; i++) {
        /* Stack: Im, T */
        lua_rawgeti(L, 2, i + 1);

        /* Stack:  Im, T, num */
        if (lua_type(L, -1) != LUA_TNUMBER) {
            free(slist);
            typerror(L, -1, "Number");
        }

        slist[i] = luaL_checkinteger(L, -1);
        lua_remove(L, -1);

        /* Stack: Im, T */
    }

    gdImageSetStyle(im, slist, size);
    free(slist);
    return 0;
}


/* void gdImageSetThickness(gdImagePtr im, int thickness) */
static int LgdImageSetThickness(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int t = luaL_checkinteger(L, 2);

    gdImageSetThickness(im, t);
    return 0;
}


/* void gdImageAlphaBlending(gdImagePtr im, int blending) */
/* Changed to: im:alphaBlending(true_or_false) */
static int LgdImageAlphaBlending(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int b = lua_toboolean(L, 2);

    gdImageAlphaBlending(im, b);
    return 0;
}


/* void gdImageSaveAlpha(gdImagePtr im, int saveFlag) */
/* Changed to: im:saveAlpha(true_or_false) */
static int LgdImageSaveAlpha(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int b = lua_toboolean(L, 2);

    gdImageSaveAlpha(im, b);
    return 0;
}


/* gdImageInterlace(gdImagePtr im, int interlace) */
/* Changed to: im:interlace(true_or_false) */
static int LgdImageInterlace(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int i = lua_toboolean(L, 2);

    gdImageInterlace(im, i);
    return 0;
}


/* void gdImageString(gdImagePtr im, gdFontPtr font, int x, int y,
        unsigned char *s, int color) */
static int LgdImageString(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdFontPtr fnt = getStdFont(L, 2);
    int x = luaL_checkinteger(L, 3);
    int y = luaL_checkinteger(L, 4);
    unsigned char *str = (unsigned char*) luaL_checkstring(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageString(im, fnt, x, y, str, c);
    return 0;
}


/* void gdImageStringUp(gdImagePtr im, gdFontPtr font, int x, int y,
        unsigned char *s, int color)  */
static int LgdImageStringUp(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdFontPtr fnt = getStdFont(L, 2);
    int x = luaL_checkinteger(L, 3);
    int y = luaL_checkinteger(L, 4);
    unsigned char *str = (unsigned char*) luaL_checkstring(L, 5);
    int c = luaL_checkinteger(L, 6);

    gdImageStringUp(im, fnt, x, y, str, c);
    return 0;
}


/* void gdImageChar(gdImagePtr im, gdFontPtr font, int x, int y,
            int c, int color)  */
/* Useless? */
static int LgdImageChar(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdFontPtr fnt = getStdFont(L, 2);
    int x = luaL_checkinteger(L, 3);
    int y = luaL_checkinteger(L, 4);
    char *str = (char*) luaL_checkstring(L, 5);
    int c = luaL_checkinteger(L, 6);
    int chr;

    if (str) {
        chr = (int) str[0];
    } else {
        typerror(L, 5, "string");
        return 0;
    }

    gdImageChar(im, fnt, x, y, chr, c);
    return 0;
}


/* void gdImageCharUp(gdImagePtr im, gdFontPtr font, int x, int y,
            int c, int color)  */
static int LgdImageCharUp(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    gdFontPtr fnt = getStdFont(L, 2);
    int x = luaL_checkinteger(L, 3);
    int y = luaL_checkinteger(L, 4);
    char *str = (char*) luaL_checkstring(L, 5);
    int c = luaL_checkinteger(L, 6);
    int chr;

    if (str)
        chr = (int) str[0];
    else {
        typerror(L, 5, "string");
        return 0;
    }

    gdImageCharUp(im, fnt, x, y, chr, c);
    return 0;
}


/* void gdImageCopy(gdImagePtr dst, gdImagePtr src, int dstX, int dstY,
            int srcX, int srcY, int w, int h) */
static int LgdImageCopy(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    int dstX = luaL_checkinteger(L, 3);
    int dstY = luaL_checkinteger(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int w = luaL_checkinteger(L, 7);
    int h = luaL_checkinteger(L, 8);

    gdImageCopy(dst, src, dstX, dstY, srcX, srcY, w, h);
    return 0;
}



/* void gdImageCopyResized(gdImagePtr dst, gdImagePtr src, int dstX,
            int dstY, int srcX, int srcY, int destW, int destH,
            int srcW, int srcH)  */
static int LgdImageCopyResized(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    int dstX = luaL_checkinteger(L, 3);
    int dstY = luaL_checkinteger(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int dstW = luaL_checkinteger(L, 7);
    int dstH = luaL_checkinteger(L, 8);
    int srcW = luaL_checkinteger(L, 9);
    int srcH = luaL_checkinteger(L, 10);

    gdImageCopyResized(dst, src, dstX, dstY, srcX, srcY, dstW, dstH,
        srcW, srcH);
    return 0;
}


/* void gdImageCopyResampled(gdImagePtr dst, gdImagePtr src, int dstX,
        int dstY, int srcX, int srcY, int destW, int destH, int srcW,
        int srcH)  */
static int LgdImageCopyResampled(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    int dstX = luaL_checkinteger(L, 3);
    int dstY = luaL_checkinteger(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int dstW = luaL_checkinteger(L, 7);
    int dstH = luaL_checkinteger(L, 8);
    int srcW = luaL_checkinteger(L, 9);
    int srcH = luaL_checkinteger(L, 10);

    gdImageCopyResampled(dst, src, dstX, dstY, srcX, srcY, dstW, dstH,
        srcW, srcH);
    return 0;
}


/* void gdImageCopyRotated(gdImagePtr dst, gdImagePtr src, double dstX,
        double dstY, int srcX, int srcY, int srcW, int srcH, int angle) */
static int LgdImageCopyRotated(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    double dstX = (double) lua_tonumber(L, 3);
    double dstY = (double) lua_tonumber(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int srcW = luaL_checkinteger(L, 7);
    int srcH = luaL_checkinteger(L, 8);
    int ang = luaL_checkinteger(L, 9);

    gdImageCopyRotated(dst, src, dstX, dstY, srcX, srcY, srcW, srcH, ang);
    return 0;
}


/* void gdImageCopyMerge(gdImagePtr dst, gdImagePtr src, int dstX,
        int dstY, int srcX, int srcY, int w, int h, int pct)  */
static int LgdImageCopyMerge(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    int dstX = luaL_checkinteger(L, 3);
    int dstY = luaL_checkinteger(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int w = luaL_checkinteger(L, 7);
    int h = luaL_checkinteger(L, 8);
    int pct = luaL_checkinteger(L, 9);

    gdImageCopyMerge(dst, src, dstX, dstY, srcX, srcY, w, h, pct);
    return 0;
}


/* void gdImageCopyMergeGray(gdImagePtr dst, gdImagePtr src, int dstX,
        int dstY, int srcX, int srcY, int w, int h, int pct) */
static int LgdImageCopyMergeGray(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);
    int dstX = luaL_checkinteger(L, 3);
    int dstY = luaL_checkinteger(L, 4);
    int srcX = luaL_checkinteger(L, 5);
    int srcY = luaL_checkinteger(L, 6);
    int w = luaL_checkinteger(L, 7);
    int h = luaL_checkinteger(L, 8);
    int pct = luaL_checkinteger(L, 9);

    gdImageCopyMergeGray(dst, src, dstX, dstY, srcX, srcY, w, h, pct);
    return 0;
}


/* void gdImagePaletteCopy(gdImagePtr dst, gdImagePtr src) */
static int LgdImagePaletteCopy(lua_State *L) {
    gdImagePtr dst = getImagePtr(L, 1);
    gdImagePtr src = getImagePtr(L, 2);

    gdImagePaletteCopy(dst, src);
    return 0;
}


/* void gdImageSquareToCircle(gdImagePtr im, int radius) */
static int LgdImageSquareToCircle(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int r = luaL_checkinteger(L, 2);

    gdImageSquareToCircle(im, r);
    return 0;
}


/* void gdImageSharpen(gdImagePtr im, int pct) */
static int LgdImageSharpen(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int pct = luaL_checkinteger(L, 2);

    gdImageSharpen(im, pct);
    return 0;
}


/* void gdImageSetClip(gdImagePtr im, int x1, int y1, int x2, int y2) */
static int LgdImageSetClip(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x1 = luaL_checkinteger(L, 2);
    int y1 = luaL_checkinteger(L, 3);
    int x2 = luaL_checkinteger(L, 4);
    int y2 = luaL_checkinteger(L, 5);

    gdImageSetClip(im, x1, y1, x2, y2);
    return 0;
}


/* void gdImageGetClip(gdImagePtr im, int *x1, int *y1, int *x2, int *y2) */
/* Changed to:  x1p, y1p, x2p, y2p = im:getClip() */
static int LgdImageGetClip(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int x1 = 0, y1 = 0, x2 = 0, y2 = 0;

    gdImageGetClip(im, &x1, &y1, &x2, &y2);
    lua_pushnumber(L, x1);
    lua_pushnumber(L, y1);
    lua_pushnumber(L, x2);
    lua_pushnumber(L, y2);
    return 4;
}


#ifdef GD_FONTCONFIG
/* int gdFTUseFontConfig(int flag) */
/* Changed to: gd.useFontConfig(true_or_false) */
static int LgdFTUseFontConfig(lua_State *L) {
    int b = lua_toboolean(L, 1);
    lua_pushboolean(L, gdFTUseFontConfig(b));
    return 1;
}
#endif


#ifdef GD_FREETYPE 
/* int gdFontCacheSetup(void) */
static int LgdFontCacheSetup(lua_State *L) {
    lua_pushboolean(L, !gdFontCacheSetup());
    return 1;
}


/* void gdFontCacheShutdown(void) */
static int LgdFontCacheShutdown(lua_State *L) {
    gdFontCacheShutdown();
    return 0;
}
#endif


/* char *gdImageStringFT(gdImagePtr im, int *brect, int fg, char *fontname,
        double ptsize, double angle, int x, int y, char *string)

 Changed To:
    llX, llY, lrX, lrY, urX, urY, ulX, ulY = im:stringFT(fg, fontname,
            ptsize, angle, x, y, string)

  Or (to get the points only):
    llX, llY, lrX, lrY, urX, urY, ulX, ulY = gd.stringFT(nil, fg,
            fontname, ptsize, angle, x, y, string)
*/

#ifdef GD_FREETYPE 
static int LgdImageStringFT(lua_State *L) {
    gdImagePtr im;
    int fg = luaL_checkinteger(L, 2);
    char *font = (char*) luaL_checkstring(L, 3);
    double size = (double) lua_tonumber(L, 4);
    double ang = (double) lua_tonumber(L, 5);
    int x = luaL_checkinteger(L, 6);
    int y = luaL_checkinteger(L, 7);
    char *str = (char*) luaL_checkstring(L, 8);
    int brect[8];

    if (lua_isnil(L, 1))
        im = NULL;
    else
        im = getImagePtr(L, 1);

    if (gdImageStringFT(im, brect, fg, font, size, ang, x, y, str) == NULL) {
        lua_pushnumber(L, brect[0]);
        lua_pushnumber(L, brect[1]);
        lua_pushnumber(L, brect[2]);
        lua_pushnumber(L, brect[3]);
        lua_pushnumber(L, brect[4]);
        lua_pushnumber(L, brect[5]);
        lua_pushnumber(L, brect[6]);
        lua_pushnumber(L, brect[7]);
        return 8;
    }

    lua_pushnil(L);
    return 1;
}


/* char *gdImageStringFT(gdImagePtr im, int *brect, int fg, char *fontname,
        double ptsize, double angle, int x, int y, char *string)

 Changed To:
    llX, llY, lrX, lrY, urX, urY, ulX, ulY [, xshow] [, fontpath] =
        im:stringFTEx(fg, fontname, ptsize, angle, x, y, string, { ... })

  Or:
    llX, llY, lrX, lrY, urX, urY, ulX, ulY [, xshow] [, fontpath] =
        gd.stringFTEx(nil, fg, fontname, ptsize, angle, x, y, string, { ... })

*/

static int LgdImageStringFTEx(lua_State *L) {
    gdImagePtr im;
    int fg = luaL_checkinteger(L, 2);
    char *font = (char*) luaL_checkstring(L, 3);
    double size = (double) lua_tonumber(L, 4);
    double ang = (double) lua_tonumber(L, 5);
    int x = luaL_checkinteger(L, 6);
    int y = luaL_checkinteger(L, 7);
    char *str = (char*) luaL_checkstring(L, 8);
    gdFTStringExtra *ex = getFTStringExtraPtr(L, 9);
    int brect[8];
    int ret = 8;

    if (lua_isnil(L, 1))
        im = NULL;
    else
        im = getImagePtr(L, 1);

    if (gdImageStringFTEx(im, brect, fg, font, size, ang, x, y, str, ex) == NULL) {
        lua_pushnumber(L, brect[0]);
        lua_pushnumber(L, brect[1]);
        lua_pushnumber(L, brect[2]);
        lua_pushnumber(L, brect[3]);
        lua_pushnumber(L, brect[4]);
        lua_pushnumber(L, brect[5]);
        lua_pushnumber(L, brect[6]);
        lua_pushnumber(L, brect[7]);
        ret = 8;
        if (ex->flags & gdFTEX_XSHOW) {
            lua_pushstring(L, ex->xshow);
            gdFree(ex->xshow);
            ret++;
        }
        if (ex->flags & gdFTEX_RETURNFONTPATHNAME) {
            lua_pushstring(L, ex->fontpath);
            gdFree(ex->fontpath);
            ret++;
        }

        free(ex);
        return ret;
    }

    lua_pushnil(L);
    return 1;
}



/* char *gdImageStringFTCircle(gdImagePtr im, int cx, int cy, double radius,
                double textRadius, double fillPortion, char *font,
                double points, char *top, char *bottom, int fgcolor)

   Changed to: im:stringFTCircle(cx, cy, radius, textRadius,
                   fillPortion, fontname, points, top, bottom, color)
*/

static int LgdImageStringFTCircle(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1);
    int cx = luaL_checkinteger(L, 2);
    int cy = luaL_checkinteger(L, 3);
    double radius = (double) lua_tonumber(L, 4);
    double textRadius = (double) lua_tonumber(L, 5);
    double fillPortion = (double) lua_tonumber(L, 6);
    char *font = (char*) luaL_checkstring(L, 7);
    double points = (double) lua_tonumber(L, 8);
    char *top = (char*) luaL_checkstring(L, 9);
    char *bottom = (char*) luaL_checkstring(L, 10);
    int color = luaL_checkinteger(L, 11);

    if (gdImageStringFTCircle(im, cx, cy, radius, textRadius, fillPortion,
        font, points, top, bottom, color))
        lua_pushboolean(L, 0);  /* Error */
    else
        lua_pushboolean(L, 1);
    return 1;
}
#endif


#ifdef GD_GIF
/* void gdImageGifAnimBegin(gdImagePtr im, FILE *out, int GlobalCM, int Loops)
    Changed to:  im:gifAnimBegin(filename, globalCM, loops)
*/

static int LgdImageGifAnimBegin(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1); 
    const char *fname = luaL_checkstring(L, 2);
    int globalCM = lua_toboolean(L, 3);
    int loops = luaL_checkinteger(L, 4);
    FILE *fp;

    if ((fp = fopen(fname, "wb")) == NULL) {
        lua_pushboolean(L, 0); /* Error */
        return 1;
    }

    gdImageGifAnimBegin(im, fp, globalCM, loops);
    fclose(fp);
    lua_pushboolean(L, 1);  /* ok */
    return 1;
}


/* void gdImageGifAnimAdd(gdImagePtr im, FILE *out, int LocalCM, int LeftOfs,
            int TopOfs, int Delay, int Disposal, gdImagePtr previm)
    Changed to:  im:gifAnimAdd(filename, localCM, leftOfs, topOfs, delay,
                    disposal [, previm])
*/

static int LgdImageGifAnimAdd(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1); 
    const char *fname = luaL_checkstring(L, 2);
    int localCM = lua_toboolean(L, 3);
    int leftOfs = luaL_checkinteger(L, 4);
    int topOfs = luaL_checkinteger(L, 5);
    int delay = luaL_checkinteger(L, 6);
    int disp = luaL_checkinteger(L, 7);
    gdImagePtr previm = NULL;
    FILE *fp;

    if (lua_gettop(L) >= 8)
        previm = getImagePtr(L, 8);

    if ((fp = fopen(fname, "ab")) == NULL) {
        lua_pushboolean(L, 0); /* Error */
        return 1;
    }

    gdImageGifAnimAdd(im, fp, localCM, leftOfs, topOfs, delay, disp, previm);
    fclose(fp);
    lua_pushboolean(L, 1);  /* ok */
    return 1;
}


/*  void gdImageGifAnimEnd(FILE *out)
    Changed to:  gd.gifAnimEnd(filename)
*/

static int LgdImageGifAnimEnd(lua_State *L) {
    const char *fname = luaL_checkstring(L, 1);
    FILE *fp;

    if ((fp = fopen(fname, "ab")) == NULL) {
        lua_pushboolean(L, 0); /* Error */
        return 1;
    }

    gdImageGifAnimEnd(fp);
    fclose(fp);
    lua_pushboolean(L, 1);  /* ok */
    return 1;
}


/* void* gdImageGifAnimBeginPtr(gdImagePtr im, int *size, int GlobalCM,
        int Loops)
    Changed to:  im:gifAnimBeginStr(globalCM, loops)
*/

static int LgdImageGifAnimBeginPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1); 
    int globalCM = lua_toboolean(L, 2);
    int loops = luaL_checkinteger(L, 3);
    char *str;
    int size;

    str = gdImageGifAnimBeginPtr(im, &size, globalCM, loops);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else
        lua_pushnil(L);
    return 1;
}


/* void* gdImageGifAnimAddPtr(gdImagePtr im, int *size, int LocalCM,
    int LeftOfs, int TopOfs, int Delay, int Disposal, gdImagePtr previm)

    Changed to: im:gifAnimAddStr(localCM, leftOfs, topOfs, delay,
                    disposal [, previm])
*/

static int LgdImageGifAnimAddPtr(lua_State *L) {
    gdImagePtr im = getImagePtr(L, 1); 
    int localCM = lua_toboolean(L, 2);
    int leftOfs = luaL_checkinteger(L, 3);
    int topOfs = luaL_checkinteger(L, 4);
    int delay = luaL_checkinteger(L, 5);
    int disp = luaL_checkinteger(L, 6);
    gdImagePtr previm = NULL;
    int size;
    char *str;

    if (lua_gettop(L) >= 7)
        previm = getImagePtr(L, 7);

    str = gdImageGifAnimAddPtr(im, &size, localCM, leftOfs, topOfs, delay,
            disp, previm);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else
        lua_pushnil(L);
    return 1;
}


/* void* gdImageGifAnimEndPtr(int *size)
    Changed to:  gd.gifAnimEndStr()
*/

static int LgdImageGifAnimEndPtr(lua_State *L) {
    int size;
    char *str;

    str = gdImageGifAnimEndPtr(&size);
    if (str != NULL) {
        lua_pushlstring(L, str, size);
        gdFree(str);
    } else
        lua_pushnil(L);
    return 1;
}

#endif



static const luaL_Reg LgdFunctions[] =
{
/*  Leave Lua do it!
    { "destroy",                LgdImageDestroy }, */

    { "create",                     LgdImageCreate },
    { "createPalette",              LgdImageCreatePalette },
    { "createTrueColor",            LgdImageCreateTrueColor },
    { "createPaletteFromTrueColor", LgdImageCreatePaletteFromTrueColor },
    { "trueColorToPalette",         LgdImageTrueColorToPalette },

#ifdef GD_JPEG
    { "createFromJpeg",         LgdImageCreateFromJpeg },
    { "createFromJpegStr",      LgdImageCreateFromJpegPtr },
#endif
#ifdef GD_GIF
    { "createFromGif",          LgdImageCreateFromGif },
    { "createFromGifStr",       LgdImageCreateFromGifPtr },
#endif
    { "createFromPng",          LgdImageCreateFromPng },
    { "createFromPngStr",       LgdImageCreateFromPngPtr },
    { "createFromGd",           LgdImageCreateFromGd },
    { "createFromGdStr",        LgdImageCreateFromGdPtr },
    { "createFromGd2",          LgdImageCreateFromGd2 },
    { "createFromGd2Str",       LgdImageCreateFromGd2Ptr },
    { "createFromGd2Part",      LgdImageCreateFromGd2Part },
    { "createFromGd2PartStr",   LgdImageCreateFromGd2PartPtr },

#ifdef GD_XPM
    { "createFromXbm",          LgdImageCreateFromXbm },
    { "createFromXpm",          LgdImageCreateFromXpm },
#endif

#ifdef GD_JPEG
    { "jpeg",                   LgdImageJpeg },
    { "jpegStr",                LgdImageJpegPtr },
#endif
#ifdef GD_PNG
    { "png",                    LgdImagePng },
    { "pngStr",                 LgdImagePngPtr },
    { "pngEx",                  LgdImagePngEx },
    { "pngStrEx",               LgdImagePngPtrEx },
#endif
#ifdef GD_GIF
    { "gif",                    LgdImageGif },
    { "gifStr",                 LgdImageGifPtr },
#endif
    { "gd",                     LgdImageGd },
    { "gdStr",                  LgdImageGdPtr },
    { "gd2",                    LgdImageGd2 },
    { "gd2Str",                 LgdImageGd2Ptr },
    { "wbmp",                   LgdImageWBMP },
    { "wbmpStr",                LgdImageWBMPPtr },

    { "colorAllocate",          LgdImageColorAllocate },
    { "colorAllocateAlpha",     LgdImageColorAllocateAlpha },
    { "colorClosest",           LgdImageColorClosest },
    { "colorClosestAlpha",      LgdImageColorClosestAlpha },
    { "colorClosestHWB",        LgdImageColorClosestHWB },
    { "colorExact",             LgdImageColorExact },
    { "colorExactAlpha",        LgdImageColorExactAlpha },
    { "colorResolve",           LgdImageColorResolve },
    { "colorResolveAlpha",      LgdImageColorResolveAlpha },
    { "colorsTotal",            LgdImageColorsTotal },
    { "red",                    LgdImageRed },
    { "blue",                   LgdImageBlue },
    { "green",                  LgdImageGreen },
    { "alpha",                  LgdImageAlpha },
    { "getTransparent",         LgdImageGetTransparent },
    { "colorTransparent",       LgdImageColorTransparent },
    { "colorDeallocate",        LgdImageColorDeallocate },

    { "boundsSafe",             LgdImageBoundsSafe },
    { "getPixel",               LgdImageGetPixel },
    { "sizeX",                  LgdImageSX },
    { "sizeY",                  LgdImageSY },
    { "sizeXY",                 LgdImageSXY },
    { "getClip",                LgdImageGetClip },
    { "setClip",                LgdImageSetClip },

    { "setPixel",               LgdImageSetPixel },
    { "line",                   LgdImageLine },
    { "rectangle",              LgdImageRectangle },
    { "filledRectangle",        LgdImageFilledRectangle },
    { "polygon",                LgdImagePolygon },
    { "filledPolygon",          LgdImageFilledPolygon },
    { "openPolygon",            LgdImageOpenPolygon },
    { "arc",                    LgdImageArc },
    { "filledArc",              LgdImageFilledArc },
    { "filledEllipse",          LgdImageFilledEllipse },
    { "fill",                   LgdImageFill },
    { "fillToBorder",           LgdImageFillToBorder },

    { "setAntiAliased",            LgdImageSetAntiAliased },
    { "setAntiAliasedDontBlend",   LgdImageSetAntiAliasedDontBlend },
    { "setBrush",                  LgdImageSetBrush },
    { "setTile",                   LgdImageSetTile },
    { "setStyle",                  LgdImageSetStyle },
    { "setThickness",              LgdImageSetThickness },
    { "alphaBlending",             LgdImageAlphaBlending },
    { "saveAlpha",                 LgdImageSaveAlpha },
    { "getInterlaced",             LgdImageGetInterlaced },
    { "interlace",                 LgdImageInterlace },

    { "string",                 LgdImageString },
    { "stringUp",               LgdImageStringUp },
    { "char",                   LgdImageChar },
    { "charUp",                 LgdImageCharUp },

    { "copy",                   LgdImageCopy },
    { "copyResized",            LgdImageCopyResized },
    { "copyResampled",          LgdImageCopyResampled },
    { "copyRotated",            LgdImageCopyRotated },
    { "copyMerge",              LgdImageCopyMerge },
    { "copyMergeGray",          LgdImageCopyMergeGray },
    { "paletteCopy",            LgdImagePaletteCopy },
    { "squareToCircle",         LgdImageSquareToCircle },
    { "sharpen",                LgdImageSharpen },

#ifdef GD_FREETYPE
    { "stringFT",               LgdImageStringFT },
    { "stringFTEx",             LgdImageStringFTEx },
    { "stringFTCircle",         LgdImageStringFTCircle },
    { "fontCacheSetup",         LgdFontCacheSetup },
    { "fontCacheShutdown",      LgdFontCacheShutdown },
#endif
    
#ifdef GD_FONTCONFIG
    { "useFontConfig",          LgdFTUseFontConfig },
#endif

#ifdef GD_GIF  /* Gif animation */
    { "gifAnimBegin",           LgdImageGifAnimBegin },
    { "gifAnimAdd",             LgdImageGifAnimAdd },
    { "gifAnimEnd",             LgdImageGifAnimEnd },
    { "gifAnimBeginStr",        LgdImageGifAnimBeginPtr },
    { "gifAnimAddStr",          LgdImageGifAnimAddPtr },
    { "gifAnimEndStr",          LgdImageGifAnimEndPtr },
#endif

    { NULL, NULL }
};


static const luaL_Reg LgdMetatable[] =
{
    { "__gc", LgdImageDestroy },
    { NULL, NULL }
};


int luaopen_gd(lua_State *L) {
    lua_newtable(L);
    luaL_setfuncs(L, LgdFunctions, 0);

    lua_pushliteral(L, "VERSION");
    lua_pushstring(L, LIB_VERSION);
    lua_settable(L, -3);

    lua_pushliteral(L, "COPYRIGHT");
    lua_pushstring(L, LIB_COPYRIGHT);
    lua_settable(L, -3);
    
    tblseticons(L, "MAX_COLORS", gdMaxColors);
    tblseticons(L, "GD2_FMT_RAW", GD2_FMT_RAW);
    tblseticons(L, "GD2_FMT_COMPRESSED", GD2_FMT_COMPRESSED);
    tblseticons(L, "ARC", gdArc);
    tblseticons(L, "CHORD", gdChord);
    tblseticons(L, "PIE", gdPie);
    tblseticons(L, "NO_FILL", gdNoFill);
    tblseticons(L, "EDGED", gdEdged);
    tblseticons(L, "ANTI_ALIASED", gdAntiAliased);
    tblseticons(L, "BRUSHED", gdBrushed);
    tblseticons(L, "STYLED", gdStyled);
    tblseticons(L, "STYLED_BRUSHED", gdStyledBrushed);
    tblseticons(L, "TILED", gdTiled);
    tblseticons(L, "TRANSPARENT", gdTransparent);

#ifdef GD_FREETYPE
    /* For gd.StringFTEx */
    tblseticons(L, "FTEX_Unicode", gdFTEX_Unicode);
    tblseticons(L, "FTEX_Shift_JIS", gdFTEX_Shift_JIS);
    tblseticons(L, "FTEX_Big5", gdFTEX_Big5);
#endif

#ifdef GD_GIF
    /* For gif animation */
    tblseticons(L, "DISPOSAL_NONE", gdDisposalNone);
    tblseticons(L, "DISPOSAL_UNKNOWN", gdDisposalUnknown);
    tblseticons(L, "DISPOSAL_RESTORE_BACKGROUND", gdDisposalRestoreBackground);
    tblseticons(L, "DISPOSAL_RESTORE_PREVIOUS", gdDisposalRestorePrevious);
#endif

    /* Standard gd fonts */
    tblseticons(L, "FONT_TINY", MY_GD_FONT_TINY);
    tblseticons(L, "FONT_SMALL", MY_GD_FONT_SMALL);
    tblseticons(L, "FONT_MEDIUM", MY_GD_FONT_MEDIUM_BOLD);
    tblseticons(L, "FONT_LARGE", MY_GD_FONT_LARGE);
    tblseticons(L, "FONT_GIANT", MY_GD_FONT_GIANT);

    luaL_newmetatable(L, GD_IMAGE_PTR_TYPENAME);
    lua_pushliteral(L, "__index");
    lua_pushvalue(L, -3);
    lua_settable(L, -3);
    luaL_setfuncs(L, LgdMetatable, 0);
    lua_pop(L, 1);

    return 1;
}

