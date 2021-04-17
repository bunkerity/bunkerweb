const express = require('express')
const app = express()
const port = 3000
var os = require("os");

app.get('/', (req, res) => {
  res.send('Container id = ' + os.hostname())
})

app.listen(port, () => {
  console.log(`Example app listening at http://localhost:${port}`)
})

