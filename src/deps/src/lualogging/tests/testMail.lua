local log_email = require"logging.email"

local logger = log_email {
  rcpt = "mail@host.com",
  from = "mail@host.com",
  {
    subject = "[%level] logging.email test",
  }, -- headers
}

logger:info("logging.email test")
logger:debug("debugging...")
logger:error("error!")

print("Mail Logging OK")

