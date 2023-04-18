local log_sock = require"logging.socket"

local logger = log_sock("localhost", "5000")

logger:info("logging.socket test")
logger:debug("debugging...")
logger:error("error!")

print("Socket Logging OK")

