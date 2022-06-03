local json = require "cjson.safe"

return {
    serialize   = json.encode,
    deserialize = json.decode,
}
