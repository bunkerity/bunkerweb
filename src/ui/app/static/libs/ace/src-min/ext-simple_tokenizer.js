define("ace/ext/simple_tokenizer",["require","exports","module","ace/tokenizer","ace/layer/text_util"],function(e,t,n){"use strict";function o(e,t){var n=new s(e,new r(t.getRules())),o=[];for(var u=0;u<n.getLength();u++){var a=n.getTokens(u);o.push(a.map(function(e){return{className:i(e.type)?undefined:"ace_"+e.type.replace(/\./g," ace_"),value:e.value}}))}return o}var r=e("../tokenizer").Tokenizer,i=e("../layer/text_util").isTextToken,s=function(){function e(e,t){this._lines=e.split(/\r\n|\r|\n/),this._states=[],this._tokenizer=t}return e.prototype.getTokens=function(e){var t=this._lines[e],n=this._states[e-1],r=this._tokenizer.getLineTokens(t,n);return this._states[e]=r.state,r.tokens},e.prototype.getLength=function(){return this._lines.length},e}();n.exports={tokenize:o}});                (function() {
                    window.require(["ace/ext/simple_tokenizer"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
