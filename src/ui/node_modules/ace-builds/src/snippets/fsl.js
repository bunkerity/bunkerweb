define("ace/snippets/fsl.snippets",["require","exports","module"], function(require, exports, module){module.exports = "snippet header\n\tmachine_name     : \"\";\n\tmachine_author   : \"\";\n\tmachine_license  : MIT;\n\tmachine_comment  : \"\";\n\tmachine_language : en;\n\tmachine_version  : 1.0.0;\n\tfsl_version      : 1.0.0;\n\tstart_states     : [];\n";

});

define("ace/snippets/fsl",["require","exports","module","ace/snippets/fsl.snippets"], function(require, exports, module){"use strict";
exports.snippetText = require("./fsl.snippets");
exports.scope = "fsl";

});                (function() {
                    window.require(["ace/snippets/fsl"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            