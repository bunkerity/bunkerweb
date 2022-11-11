-- load the smtp support and its friends
local smtp = require("socket.smtp")
local mime = require("mime")
local ltn12 = require("ltn12")

function filter(s)
    if s then io.write(s) end
    return s
end

source = smtp.message {
    headers = { ['content-type'] = 'multipart/alternative' },
    body = {
        [1] = {
            headers = { ['Content-type'] = 'text/html' },
            body = "<html> <body> Hi, <b>there</b>...</body> </html>"
        },
        [2] = {
            headers = { ['content-type'] = 'text/plain' },
            body = "Hi, there..."
        }
    }
}

r, e = smtp.send{
    rcpt = {"<diego@tecgraf.puc-rio.br>",
            "<diego@princeton.edu>" },
    from = "<diego@princeton.edu>",
    source = ltn12.source.chain(source, filter),
    --server = "mail.cs.princeton.edu"
    server = "localhost",
    port = 2525
}

print(r, e)

-- creates a source to send a message with two parts. The first part is 
-- plain text, the second part is a PNG image, encoded as base64.
source = smtp.message{
  headers = {
     -- Remember that headers are *ignored* by smtp.send. 
     from = "Sicrano <sicrano@tecgraf.puc-rio.br>",
     to = "Fulano <fulano@tecgraf.puc-rio.br>",
     subject = "Here is a message with attachments"
  },
  body = {
    preamble = "If your client doesn't understand attachments, \r\n" ..
               "it will still display the preamble and the epilogue.\r\n" ..
               "Preamble might show up even in a MIME enabled client.",
    -- first part: No headers means plain text, us-ascii.
    -- The mime.eol low-level filter normalizes end-of-line markers.
    [1] = { 
      body = mime.eol(0, [[
        Lines in a message body should always end with CRLF. 
        The smtp module will *NOT* perform translation. It will
        perform necessary stuffing, though.
      ]])
    },
    -- second part: Headers describe content the to be an image, 
    -- sent under the base64 transfer content encoding.
    -- Notice that nothing happens until the message is sent. Small 
    -- chunks are loaded into memory and translation happens on the fly.
    [2] = { 
      headers = {
        ["ConTenT-tYpE"] = 'image/png; name="luasocket.png"',
        ["content-disposition"] = 'attachment; filename="luasocket.png"',
        ["content-description"] = 'our logo',
        ["content-transfer-encoding"] = "BASE64"
      },
      body = ltn12.source.chain(
        ltn12.source.file(io.open("luasocket.png", "rb")),
        ltn12.filter.chain(
          mime.encode("base64"),
          mime.wrap()
        )
      )
    },
    epilogue = "This might also show up, but after the attachments"
  }
}


r, e = smtp.send{
    rcpt = {"<diego@tecgraf.puc-rio.br>",
            "<diego@princeton.edu>" },
    from = "<diego@princeton.edu>",
    source = ltn12.source.chain(source, filter),
    --server = "mail.cs.princeton.edu",
    --port = 25
    server = "localhost",
    port = 2525
}

print(r, e)


