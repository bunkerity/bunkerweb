'use strict';

var path = require('path');

module.exports = {
  devtool: 'sourcemap',
  entry: {
    app: ['./src/index.ts']
  },
  output: {
    path: path.join(__dirname, 'dist'),
    publicPath: 'dist',
    filename: 'json-formatter.js',
    library: 'JSONFormatter',
    libraryTarget: 'commonjs2',
    umdNamedDefine: true
  },
  resolve: {
    extensions: ['.ts', '.less']
  },
  module: {
    rules: [
      {
        test: /\.less$/,
        use: [
          "style-loader",
          "css-loader",
          "less-loader"
        ]
      },
      {
        test: /\.ts$/,
        loader: 'ts-loader'
      }
    ]
  },
  optimization: {
    minimize: true
  }
};
