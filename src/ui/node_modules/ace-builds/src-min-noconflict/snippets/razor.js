ace.define("ace/snippets/razor.snippets",["require","exports","module"],function(e,t,n){n.exports="snippet if\n(${1} == ${2}) {\n	${3}\n}"}),ace.define("ace/snippets/razor",["require","exports","module","ace/snippets/razor.snippets"],function(e,t,n){"use strict";t.snippetText=e("./razor.snippets"),t.scope="razor"});                (function() {
                    ace.require(["ace/snippets/razor"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            