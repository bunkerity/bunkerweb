"""Real bundled ban, CAPTCHA and middleclass contracts; only runtime boundaries faked."""

from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
package.path = ROOT .. '/src/common/core/?.lua;' .. ROOT .. '/src/bw/lua/?.lua;' .. package.path
package.loaded['cjson'] = json
LOGS, RESPONSE = {}, {}
ngx = {ERR='ERR', DEBUG='DEBUG', header={},
    log=function(level, message) LOGS[#LOGS+1]={level,message} end,
    redirect=function(location) RESPONSE.redirect=location end,
    say=function(text) RESPONSE.body=text end,
    exit=function(status) RESPONSE.exit=status end,
    encode_args=function(args) ENCODED=args; return json.encode(args) end}
for code, name in pairs({[200]='OK',[202]='ACCEPTED',[204]='NO_CONTENT',[301]='MOVED_PERMANENTLY',
    [302]='MOVED_TEMPORARILY',[400]='BAD_REQUEST',[401]='UNAUTHORIZED',[403]='FORBIDDEN',
    [404]='NOT_FOUND',[405]='NOT_ALLOWED',[406]='NOT_ACCEPTABLE',[444]='CLOSE',[500]='INTERNAL_SERVER_ERROR'}) do
    ngx['HTTP_' .. name]=code
end
HTTP_STATUS, HTTP_BODY, CLOSED, REQUESTS = 200, '{"success":true}', 0, {}
package.loaded['resty.http'] = {new=function()
    return {set_timeout=function(_, ms) TIMEOUT=ms end,
        request_uri=function(_, url, opts)
            REQUESTS[#REQUESTS+1]={url=url,options=opts}
            if HTTP_ERROR then return nil, HTTP_ERROR end
            return {status=HTTP_STATUS,body=HTTP_BODY}
        end,
        close=function() CLOSED=CLOSED+1 end}
end}
"""


def run(module, body):
    return last_json(run_lua(BASE_LUA + f"\nROOT={to_lua(str(ROOT))}\n" + HARNESS + f"\nlocal lib=require('{module}')\n" + body))


def page(tmp_path):
    path = tmp_path / "template.html"
    path.write_text("{{captcha_site_key}}|{{captcha_frontend_js}}|{{captcha_frontend_key}}\n")
    return to_lua(str(path))


@pytest.mark.parametrize("code", [None, 0, "", "999", "401"])
def test_ban_status_default_supported_and_unsupported(code):
    out = run(
        "crowdsec.lib.ban",
        f"lib.new('', '', {to_lua(code)}); lib.apply(); emit({{response=RESPONSE,logs=LOGS}})",
    )
    expected = 401 if code == "401" else 403
    assert out["response"] == {"exit": expected}
    assert any(f"will return HTTP {expected}" in message for _, message in out["logs"])
    assert any("not supported" in message for _, message in out["logs"]) == (code == "999")


def test_ban_template_sets_status_headers_and_body(tmp_path):
    path = tmp_path / "ban.html"
    path.write_text("Denied\n")
    out = run(
        "crowdsec.lib.ban",
        f"lib.new({to_lua(str(path))}, '', '403'); lib.apply(429); " "emit({response=RESPONSE,status=ngx.status,headers=ngx.header})",
    )
    assert out == {"response": {"exit": 429, "body": "Denied"}, "status": 429, "headers": {"content_type": "text/html", "cache_control": "no-cache"}}


def test_ban_redirect_takes_precedence_over_template(tmp_path):
    out = run(
        "crowdsec.lib.ban",
        f"lib.new({page(tmp_path)}, '/blocked', '403'); lib.apply(); emit({{response=RESPONSE,headers=ngx.header}})",
    )
    assert out == {"response": {"redirect": "/blocked"}, "headers": {}}


@pytest.mark.parametrize("path", [None, "", "/nonexistent-l4f-ban-template"])
def test_ban_missing_template_returns_forbidden(path):
    assert run("crowdsec.lib.ban", f"lib.new({to_lua(path)}, '', nil); lib.apply(); emit(RESPONSE)") == {"exit": 403}


@pytest.mark.xfail(strict=True, reason="Bundled ban.new accepts nil redirect but ban.apply concatenates it, crashing instead of denying")
def test_ban_nil_redirect_still_denies():
    assert run("crowdsec.lib.ban", "lib.new(nil,nil,nil); lib.apply(); emit(RESPONSE)") == {"exit": 403}


@pytest.mark.parametrize(
    ("site", "secret", "provider", "error"),
    [
        ("site", "secret", "unknown", "unsupported captcha provider"),
        ("", "secret", "recaptcha", "no captcha site key provided"),
        (None, "secret", "recaptcha", "no captcha site key provided"),
        ("site", "", "recaptcha", "no captcha secret key provided"),
        ("site", False, "recaptcha", "no captcha secret key provided"),
    ],
)
def test_captcha_configuration_rejects_invalid_keys(tmp_path, site, secret, provider, error):
    out = run(
        "crowdsec.lib.captcha",
        f"local c,e=lib.New({to_lua(site)},{to_lua(secret)},{page(tmp_path)},{to_lua(provider)}); emit({{missing=c==nil,error=e}})",
    )
    assert out == {"missing": True, "error": error}


@pytest.mark.parametrize("path", [None, "/nonexistent-l4f-captcha-template"])
def test_captcha_missing_template_rejected(path):
    assert run("crowdsec.lib.captcha", f"local c,e=lib.New('site','secret',{to_lua(path)},'recaptcha'); emit(e)") == "captcha template file does not exist"


@pytest.mark.parametrize(
    ("provider", "host", "frontend", "key"),
    [
        ("recaptcha", "www.recaptcha.net/recaptcha/api/siteverify", "www.recaptcha.net/recaptcha/api.js", "g-recaptcha"),
        ("hcaptcha", "hcaptcha.com/siteverify", "js.hcaptcha.com/1/api.js", "h-captcha"),
        ("turnstile", "challenges.cloudflare.com/turnstile/v0/siteverify", "challenges.cloudflare.com/turnstile/v0/api.js", "cf-turnstile"),
    ],
)
def test_captcha_provider_template_verification_and_instance_isolation(tmp_path, provider, host, frontend, key):
    out = run(
        "crowdsec.lib.captcha",
        f"""
local c=assert(lib.New('site','secret',{page(tmp_path)},{to_lua(provider)}))
local other=assert(lib.New('other','other-secret',{page(tmp_path)},'turnstile'))
local ok,e=c.Validate('token','192.0.2.1')
emit({{ok=ok,error=e,key=c.GetCaptchaBackendKey(),view=c.GetTemplate(),request=REQUESTS[1],
    encoded=ENCODED,timeout=TIMEOUT,closed=CLOSED,other=other.GetTemplate()}})
""",
    )
    assert out["ok"] is True
    assert "error" not in out
    assert out["key"] == key + "-response"
    assert out["view"] == f"site|https://{frontend}|{key}"
    assert out["other"].startswith("other|")
    assert out["request"]["url"] == "https://" + host
    opts = out["request"]["options"]
    assert opts["method"] == "POST" and opts["ssl_verify"] is True
    assert opts["headers"] == {"Content-Type": "application/x-www-form-urlencoded"}
    assert out["encoded"] == {"secret": "secret", "response": "token", "remoteip": "192.0.2.1"}
    assert out["timeout"] == 2000 and out["closed"] == 1


@pytest.mark.parametrize(("token", "ip"), [(None, "192.0.2.1"), ("", "192.0.2.1"), (False, "192.0.2.1"), ("token", None)])
def test_captcha_missing_or_invalid_token_refused_without_request(tmp_path, token, ip):
    out = run(
        "crowdsec.lib.captcha",
        f"local c=assert(lib.New('site','secret',{page(tmp_path)},'recaptcha')); "
        f"local ok,e=c.Validate({to_lua(token)},{to_lua(ip)}); emit({{ok=ok,error=e,requests=#REQUESTS}})",
    )
    assert out == {"ok": False, "error": "invalid captcha verification input", "requests": 0}


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        ("HTTP_ERROR='timeout'", "captcha provider request failed"),
        ("HTTP_STATUS=503", "captcha provider returned HTTP 503"),
        ("HTTP_BODY='broken'", "invalid captcha provider response"),
        ("HTTP_BODY='42'", "invalid captcha provider response"),
        ("HTTP_BODY='{}'", "invalid captcha provider response"),
        ("HTTP_BODY='null'", "invalid captcha provider response"),
        ('HTTP_BODY=\'{"success":"true"}\'', "invalid captcha provider response"),
        ("HTTP_BODY='{\"success\":false}'", None),
    ],
)
def test_captcha_wrong_token_and_provider_failure_refused(tmp_path, setup, error):
    out = run(
        "crowdsec.lib.captcha",
        f"{setup}; local c=assert(lib.New('site','secret',{page(tmp_path)},'recaptcha')); "
        "local ok,e=c.Validate('wrong','192.0.2.1'); emit({ok=ok,error=e or json.null,closed=CLOSED})",
    )
    assert out == {"ok": False, "error": error, "closed": 1}


GD = r"""
IMAGES = {}
package.loaded['gd']={createTrueColor=function(w,h)
    local im={width=w,height=h,text='',colors={},lines={},files={}}
    IMAGES[#IMAGES+1]=im
    function im:colorAllocate(r,g,b)
        self.colors[#self.colors+1]={r or json.null,g or json.null,b or json.null}
        return #self.colors
    end
    function im:filledRectangle(x,y,w,h,color) self.background=color end
    function im:stringFT(color,font,size,angle,x,y,text)
        self.text=self.text..text; self.font=font; self.foreground=color
        return x,y,x+20,y,x+20,y-20,x,y-20
    end
    function im:polygon(points,color) assert(#points==4 and color==self.background) end
    function im:line(...) self.lines[#self.lines+1]={...} end
    function im:jpeg(path,quality) self.files.jpeg={path,quality} end
    function im:png(path) self.files.png=path end
    function im:pngStr() return 'PNG:'..self.text end
    function im:jpegStr(quality) return 'JPEG:'..self.text..':'..quality end
    return im
end}
local real_open=io.open
io.open=function(path,mode)
    if path~='/dev/urandom' then return real_open(path,mode) end
    if NO_URANDOM then return nil end
    return {read=function() if not EMPTY_URANDOM then return string.rep('a',32) end end,close=function() end}
end
local lib=dofile(ROOT .. '/src/common/core/antibot/captcha.lua')
"""


def image(body):
    return last_json(run_lua(BASE_LUA + f"\nROOT={to_lua(str(ROOT))}\n" + GD + body))


def test_antibot_image_draws_requested_text_and_exports():
    out = image(r"""
local c=lib.new(); c:string('Ab9'); c:font('/font.ttf'); c:line(true); c:scribble(2); c:generate()
assert(c:getStr()=='Ab9')
c:jpeg('/one.jpg',81); c:png('/one.png')
local written=c:write('/two.jpg',93)
local im=IMAGES[1]
emit({im={width=im.width,height=im.height,text=im.text,font=im.font,background=im.background,
    foreground=im.foreground,colors=im.colors,lines=im.lines,files=im.files},
    png=c:pngStr(),jpeg=c:jpegStr(70),written=written,count=#IMAGES})
""")
    assert out["written"] == "Ab9" and out["count"] == 1
    assert out["png"] == "PNG:Ab9" and out["jpeg"] == "JPEG:Ab9:70"
    im = out["im"]
    assert (im["width"], im["height"], im["text"], im["font"]) == (120, 45, "Ab9", "/font.ttf")
    assert im["background"] == 2 and im["foreground"] == 1
    assert im["colors"] == [[0, 0, 0], [255, 255, 255]]
    assert len(im["lines"]) == 5
    assert im["lines"][:3] == [[10, 10, 110, 40, 1], [11, 11, 109, 41, 1], [12, 12, 108, 42, 1]]
    assert im["files"] == {"jpeg": ["/two.jpg", 93], "png": "/one.png"}


@pytest.mark.parametrize("setup", ["", "EMPTY_URANDOM=true"])
def test_antibot_generated_text_matches_image_and_write_generates_once(setup):
    out = image(setup + r"""
local c=lib.new(); c:alphabet('Z'); c:length(4); c:scribble(); c:font('/font.ttf')
local text=c:write('/generated.jpg',90)
emit({text=text,drawn=IMAGES[1].text,width=IMAGES[1].width,lines=#IMAGES[1].lines})
""")
    assert out == {"text": "ZZZZ", "drawn": "ZZZZ", "width": 160, "lines": 20}


@pytest.mark.parametrize("alphabet", [None, ""])
def test_antibot_default_length_and_alphabet(alphabet):
    out = image(f"local c=lib.new(); c:alphabet({to_lua(alphabet)}); c:generate(); emit({{text=c:getStr(),drawn=IMAGES[1].text}})")
    assert len(out["text"]) == 6 and out["text"].isascii() and out["text"].isalpha()
    assert out["drawn"] == out["text"]


def test_antibot_custom_rgb_colors_reach_image():
    out = image("local c=lib.new(); c:string('A'); c:bgcolor(1,2,3); c:fgcolor(4,5,6); c:generate(); emit(IMAGES[1].colors)")
    assert out == [[0, 0, 0], [255, 255, 255], [1, 2, 3], [4, 5, 6]]


@pytest.mark.xfail(strict=True, reason="Bundled CAPTCHA fallback feeds math.random() fraction to Lua 5.4 randomseed, which requires an integer")
def test_antibot_without_urandom_still_generates_text():
    assert image("NO_URANDOM=true; local c=lib.new(); c:alphabet('Z'); c:length(1); c:generate(); emit(c:getStr())") == "Z"


def test_middleclass_index_fallback_inheritance_and_method_reset():
    assert (
        run(
            "middleclass",
            r"""
local A=lib('A'); function A:initialize(value) self.value=value end
function A:answer() return self.value end
A.static.kind='base'
local B=lib('B',A); local C=B:subclass('C')
assert(tostring(A)=='class A' and tostring(B(7))=='instance of class B')
assert(C(9):answer()==9 and C.kind=='base' and B.answer==A.answer)
assert(C:isSubclassOf(A) and C:isSubclassOf(B) and not A:isSubclassOf(C))
assert(C(4):isInstanceOf(A) and C(4):isInstanceOf(C) and not C(4):isInstanceOf('A'))
function B:answer() return 42 end
function A:answer() return -1 end
assert(B(7):answer()==42 and C(7):answer()==42 and A(7):answer()==-1)
B.answer=nil; assert(C(7):answer()==-1)
A.__index=function(self,key) return 'fallback:'..key end
assert(A(2).value==2 and A(2).missing=='fallback:missing' and B(3).missing=='fallback:missing')
A.__index={missing='table fallback'}
assert(A(2).missing=='table fallback' and type(A(2).answer)=='function')
A.__index=nil; assert(A(2).missing==nil and A(2):answer()==-1)
emit(true)
""",
        )
        is True
    )


def test_middleclass_mixins_hooks_allocation_and_invalid_calls():
    assert (
        run(
            "middleclass",
            r"""
local A=lib.class('A'); local hook
A.static.subclassed=function(self,other) hook=other end
local B=A:subclass('B'); assert(hook==B)
local mixin={value=12,static={kind='mixed'},included=function(self,cls) cls.static.included=self end}
assert(B:include(mixin,{extra=13})==B and B.kind=='mixed' and B.included==mixin)
local b=B(); assert(b.value==12 and b.extra==13 and b:isInstanceOf(A))
assert(B:allocate().class==B and not b:isInstanceOf(lib('Unrelated')))
for _,fn in ipairs({function() lib(1) end,function() B:subclass(false) end,
    function() B:include(false) end,function() B.static.new(false) end,
    function() B.static.allocate(false) end,function() B.static.subclass(false,'X') end,
    function() B.static.include(false,{}) end}) do assert(not pcall(fn)) end
emit(true)
""",
        )
        is True
    )
