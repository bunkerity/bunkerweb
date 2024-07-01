
local test = {
  "generic.lua",
  "testEnv.lua",
  "testConsole.lua",
  "testFile.lua",
  "testMail.lua",
  "testSocket.lua",
  "testSQL.lua",
  "testRollingFile.lua",
}

print ("Start of Logging tests")
for _, filename in ipairs(test) do
  dofile(filename)
end
print ("End of Logging tests")

