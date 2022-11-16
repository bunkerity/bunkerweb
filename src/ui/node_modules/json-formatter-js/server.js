'use strict';
var webpack = require('webpack');
var webpackDevServer = require('webpack-dev-server');
var PORT = process.env.PORT || 8080;
var config = require("./webpack.config.js");
config.entry.app.unshift(`webpack-dev-server/client?http://localhost:{PORT}/`, "webpack/hot/dev-server");
var compiler = webpack(config);
var server = new webpackDevServer(compiler, {
  progress: true,
  quiet: true,
  publicPath: config.output.publicPath
});
server.listen(PORT, console.log.bind(null, `Development server started at http://localhost:${PORT}`));