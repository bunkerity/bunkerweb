import typescript from 'rollup-plugin-typescript2';
import { terser } from 'rollup-plugin-terser';
import less from 'rollup-plugin-less';
import pkg from './package.json';

export default {
 input: 'src/index.ts',
 output: [
  {
   file: pkg.main,
   format: 'cjs'
  },
  {
   file: pkg.module,
   format: 'es'
  },
  {
   file: pkg.browser,
   format: 'umd',
   name: 'JSONFormatter'
  }
 ],
 external: [
  ...Object.keys(pkg.dependencies || {})
 ],
 plugins: [
  typescript({
   typescript: require('typescript'),
   include: [ "src/*.ts+(|x)" ],
   verbosity: 3
  }),
  terser(), // minifies generated bundles
  less({
    insert: true,
    output: 'dist/json-formatter.css'
  }),
 ]
};
