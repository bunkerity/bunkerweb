The Nginx module for adding cookie flag
==========

[![License](http://img.shields.io/badge/license-BSD-brightgreen.svg)](https://github.com/Airis777/nginx_cookie_flag_module/blob/master/LICENSE)

The Nginx module for adding cookie flag

## Dependencies
* [nginx](http://nginx.org)

## Compatibility
* 1.11.x (last tested: 1.11.2)

Earlier versions is not tested.

## Installation

1. Clone the git repository.

  ```
  git clone git://github.com:AirisX/nginx_cookie_flag_module.git
  ```

2. Add the module to the build configuration by adding
  `--add-module=/path/to/nginx_cookie_flag_module`
   or
  `--add-dynamic-module=/path/to/nginx_cookie_flag_module`

3. Build the nginx binary.

4. Install the nginx binary.

## Synopsis

```Nginx
location / {
    set_cookie_flag Secret HttpOnly secure SameSite;
    set_cookie_flag * HttpOnly;
    set_cookie_flag SessionID SameSite=Lax secure;
    set_cookie_flag SiteToken SameSite=Strict;
}
```

## Description
This module for Nginx allows to set the flags "**HttpOnly**", "**secure**" and "**SameSite**" for cookies in the "*Set-Cookie*" response headers.
The register of letters for the flags doesn't matter as it will be converted to the correct value. The order of cookie declaration among multiple directives doesn't matter too.
It is possible to set a default value using symbol "*". In this case flags will be added to the all cookies if no other value for them is overriden.

## Directives

### set_cookie_flag

-| -
--- | ---
**Syntax**  | **set_cookie_flag** \<cookie_name\|*\> [HttpOnly] [secure] [SameSite\|SameSite=[Lax\|Strict]];
**Default** | -
**Context** | server, location

Description: Add flag to desired cookie.

## Author
Anton Saraykin [<Airisenator@gmail.com>]