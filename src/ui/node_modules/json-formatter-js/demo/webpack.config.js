
var path = require('path');

module.exports = {
    devtool: 'sourcemap',
    context: __dirname,
    entry: './index.js',
    output: {
        path: path.join(__dirname, '../dist/demo'),
        filename: 'index.js'
    }
}