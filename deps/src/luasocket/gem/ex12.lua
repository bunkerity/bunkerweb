local smtp = require"socket.smtp"
local mime = require"mime"
local ltn12 = require"ltn12"

CRLF = "\013\010"

local message = smtp.message{
  headers = {
    from = "Sicrano <sicrano@example.com>",
    to = "Fulano <fulano@example.com>",
    subject = "A message with an attachment"},
  body = {
    preamble = "Hope you can see the attachment" .. CRLF,
    [1] = {
      body = "Here is our logo" .. CRLF},
    [2] = {
      headers = {
        ["content-type"] = 'image/png; name="luasocket.png"',
        ["content-disposition"] =
          'attachment; filename="luasocket.png"',
        ["content-description"] = 'LuaSocket logo',
        ["content-transfer-encoding"] = "BASE64"},
      body = ltn12.source.chain(
        ltn12.source.file(io.open("luasocket.png", "rb")),
        ltn12.filter.chain(
          mime.encode("base64"),
          mime.wrap()))}}}

assert(smtp.send{
  rcpt = "<diego@cs.princeton.edu>",
  from = "<diego@cs.princeton.edu>",
  server = "localhost",
  port = 2525,
  source = message})
