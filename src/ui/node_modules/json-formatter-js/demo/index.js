var live = document.getElementById('live');
var hoverPreviewEnabledCheckbox = document.getElementById('hoverPreviewEnabled');

function render() {
    live.style.backgroundColor = 'transparent';
    var result = document.getElementById('live-result');
    try {
        var formatter = new JSONFormatter(JSON.parse(live.value), 1, { hoverPreviewEnabled: hoverPreviewEnabledCheckbox.checked });
        result.innerHTML = '';
        result.appendChild(formatter.render());
    } catch (e) {
        live.style.backgroundColor = 'rgba(255, 87, 34, 0.35)';
    }
}
live.addEventListener('keyup', render);
hoverPreviewEnabledCheckbox.addEventListener('change', render);
render();


var complex = {
    numbers: [
        1,
        2,
        3
    ],
    boolean: true,
    'null': null,
    number: 123,
    anObject: {
        a: 'b',
        e: 'd',
        c: 'f\"'
    },
    string: 'Hello World',
    url: 'https://github.com/mohsen1/json-formatter-js',
    date: new Date(),
    func: function add(a, b) { return a + b; }
};

var deep = { a: { b: { c: { d: {} } } } };

var examples = [
    { title: 'Complex', json: complex },
    { title: 'Number', json: 42 },
    { title: 'null', json: null },
    { title: 'Empty Object', json: Object.create(null) },
    { title: 'Empty Array', json: [] },
    { title: 'Deep', json: deep },
    { title: 'Dark', json: complex, config: { theme: 'dark' } },
    { title: 'Sorted Keys', json: complex, config: { sortPropertiesBy: (a, b) => a > b } }
];

var result = document.querySelector('.result');

examples.forEach(function (example) {
    var title = document.createElement('h3');
    var formatter = new JSONFormatter(example.json, 1, example.config);

    title.innerText = example.title;

    result.appendChild(title)
    var el = formatter.render();

    if (example.config && example.config.theme === 'dark') {
        el.style.backgroundColor = '#1E1E1E';
    }

    result.appendChild(el);
});

fetch('demo/giant.json').then(function (resp) {
    resp.json().then(function (giant) {
        var giantFormatter = new JSONFormatter(giant, 2, { hoverPreviewEnabled: true });
        var title = document.createElement('h3');

        title.innerText = 'Giant JSON';
        result.appendChild(title);

        console.time('Rendering giant JSON');
        result.appendChild(giantFormatter.render());
        console.timeEnd('Rendering giant JSON');
    });
})