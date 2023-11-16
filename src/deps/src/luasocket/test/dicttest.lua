local dict = require"socket.dict"

print(dict.get("dict://localhost/d:teste"))

for i,v in pairs(dict.get("dict://localhost/d:teste")) do print(v) end
