# Vuejs

## Principle

We can develop the front-end using Vue and Vite framework.
I have all my front-end logic inside `client` folder.

We can use all the facilities of the framework, for this example you have :

- `component` folder : create a component to use in your page
- `pages` folder : contains each pages to render, we have only one page test ATM

Inside `pages` folder, you have 3 files :

- `index.html` that is entry point, we define entry point for Vue app and a div with attribut data-flask to store futur data from template
- `test.js` is js entry point that define the Vue components, plugins and settings to use for this page
- `Test.vue` is the page (global context) where we are importing components, executing logic... For example, we are retrieving data-flask from here

We have others files for the configuration of node modules and Vite.

We need to work on the front-end here, then build and move to flask app the resources when needed.

## Installation

- Need to install `node.js` and `npm` on computer
- Go inside `vuejs` folder and run `node build.js`
- Run `flask --app main.py run` then access `/test` to get Vue.js rendering app using flask data `Title from Flask !`
- `/test2` is case with no flask data (can be handle on a div or directly on Vue app)

# jsdoc

We can create a markdown documentation for components.

- `npm install -g documentation` will add lib that format js to doc
- set input and output folder in `vue2md.js`
- once done, run `node vue2md.js`, this will format .vue to .js, run subprocess to render .js to .md for each file, and finally script will merge in order and by path all .md files
