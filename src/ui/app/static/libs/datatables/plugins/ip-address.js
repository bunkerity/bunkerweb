/*! © SpryMedia Ltd, Dominique Fournier, Brad Wasson, Peter Vilhan, Kevin Gilkey-Graham - datatables.net/license */

(function( factory ){
	if ( typeof define === 'function' && define.amd ) {
		// AMD
		define( ['jquery', 'datatables.net'], function ( $ ) {
			return factory( $, window, document );
		} );
	}
	else if ( typeof exports === 'object' ) {
		// CommonJS
		var jq = require('jquery');
		var cjsRequires = function (root, $) {
			if ( ! $.fn.dataTable ) {
				require('datatables.net')(root, $);
			}
		};

		if (typeof window === 'undefined') {
			module.exports = function (root, $) {
				if ( ! root ) {
					// CommonJS environments without a window global must pass a
					// root. This will give an error otherwise
					root = window;
				}

				if ( ! $ ) {
					$ = jq( root );
				}

				cjsRequires( root, $ );
				return factory( $, root, root.document );
			};
		}
		else {
			cjsRequires( window, jq );
			module.exports = factory( jq, window, window.document );
		}
	}
	else {
		// Browser
		factory( jQuery, window, document );
	}
}(function( $, window, document ) {
'use strict';
var DataTable = $.fn.dataTable;


/**
 * Sorts a column containing IP addresses (IPv4 and IPv6) or IPv4 address and port delimited by ':' in typical dot
 * notation / colon. This can be most useful when using DataTables for a
 * networking application, and reporting information containing IP address.
 *
 *  @name IP addresses
 *  @summary Sort IP addresses numerically
 *  @author Dominique Fournier
 *  @author Brad Wasson
 *  @author Peter Vilhan
 *  @author Kevin Gilkey-Graham
 *
 *  @example
 *    $('#example').dataTable( {
 *       columnDefs: [
 *         { type: 'ip-address', targets: 0 }
 *       ]
 *    } );
 */
DataTable.ext.type.order['ip-address-pre'] = function (a) {
    var i, item;
    var m, n, t, p;
    var x, xa;
    if (!a) {
        return '000000000000';
    }
    a = a.replace(/<[\s\S]*?>/g, '');
    //IPv4:Port
    t = a.split(':');
    if (t.length == 2) {
        m = t[0].split('.');
        p = t[1];
    }
    else {
        m = a.split('.');
    }
    n = a.split(':');
    x = '';
    xa = '';
    if (m.length == 4) {
        // IPV4
        for (i = 0; i < m.length; i++) {
            item = m[i];
            x += '000'.substr(item.length) + item;
        }
        if (p) {
            x += ':' + '00000'.substr(p.length) + p;
        }
    }
    else if (n.length > 0) {
        // IPV6
        var count = 0;
        for (i = 0; i < n.length; i++) {
            item = n[i];
            if (i > 0) {
                xa += ':';
            }
            if (item.length === 0) {
                count += 0;
            }
            else {
                xa += '0000'.substr(item.length) + item;
                count += 4;
            }
        }
        // Padding the ::
        n = xa.split(':');
        var paddDone = 0;
        for (i = 0; i < n.length; i++) {
            item = n[i];
            if (item.length === 0 && paddDone === 0) {
                for (var padding = 0; padding < 32 - count; padding++) {
                    x += '0';
                    paddDone = 1;
                }
            }
            else {
                x += item;
            }
        }
    }
    return x;
};


return DataTable;
}));
