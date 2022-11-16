# JSON Formatter

[![Build Status](https://travis-ci.org/mohsen1/json-formatter-js.svg?branch=master)](https://travis-ci.org/mohsen1/json-formatter-js)

> Render JSON objects in HTML with a **collapsible** navigation.

JSON Formatter started as an [AngularJS directive](https://github.com/mohsen1/json-formatter). This is pure JavaScript implementation of the same module.

**[Live Demo](http://azimi.me/json-formatter-js/)**

### Usage

Install via npm

```shell
npm install --save json-formatter-js
```
include `json-formatter.js` from `dist` folder in your page.
```js
import JSONFormatter from 'json-formatter-js'

const myJSON = {ans: 42};

const formatter = new JSONFormatter(myJSON);

document.body.appendChild(formatter.render());

```

### API

#### `JSONFormatter(json [, open [, config] ])`

##### `json` (`Object`) - **required**
The JSON object you want to render. It has to be an object or array. Do NOT pass raw JSON string.
##### `open` (`Number`)
Default: `1`
This number indicates up to how many levels the rendered tree should expand. Set it to `0` to make the whole tree collapsed or set it to `Infinity` to expand the tree deeply
##### `config` (`Object`)
Default:
```js
{
  hoverPreviewEnabled: false,
  hoverPreviewArrayCount: 100,
  hoverPreviewFieldCount: 5,
  theme: '',
  animateOpen: true,
  animateClose: true,
  useToJSON: true
}
```
Available configurations:
##### Hover Preview
* `hoverPreviewEnabled`:  enable preview on hover.
* `hoverPreviewArrayCount`: number of array items to show in preview Any array larger than this number will be shown as `Array[XXX]` where `XXX` is length of the array.
* `hoverPreviewFieldCount`: number of object properties to show for object preview. Any object with more properties that thin number will be truncated.

##### Theme
* `theme`: a string that can be any of these options: `['dark']`. Look at [`src/style.less`](src/style.less) for making new themes.

##### Animation
* `animateOpen`: enable animation when expanding json object. True by default.
* `animateClose`: enable animation when closing json object. True by default.

##### Rendering Options
* `useToJSON`: use the toJSON method to render an object as a string as available. Usefull for objects like Date or Mongo's ObjectID that migh make more sense as a strign than as empty objects. True by default.

* `sortPropertiesBy`: use the given sorting function to deeply sort the object properties.

#### `openAtDepth([depth])`

```js
const formatter = new Formatter({ ... });
document.body.appendChild(formatter.render());
formatter.openAtDepth(3);
```

##### `depth` (`Number`)
Default: `1`
This number indicates up to how many levels the rendered tree should open. It allows use cases such as collapse all levels (with value `0`) or expand all levels (with value `Infinity`).

### Development
Install the dependencies:

```
npm install
```

Run the dev server

```
npm start
```

#### Running tests

**Once:**

```shell
npm test
```

### License
[MIT](./LICENSE)
