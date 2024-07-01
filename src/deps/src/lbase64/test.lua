local base64 = require('base64')

local function test( s, b64 )
	assert( base64.encode( s ) == b64 )
	assert( base64.decode( b64 ) == s )
	assert( base64.decode( base64.encode( s )) == s )
	assert( base64.encode( s, nil, true ) == b64 )
	assert( base64.decode( b64, nil, true ) == s )
	assert( base64.decode( base64.encode( s, nil, true ), nil, true ) == s )
end

test( 'any carnal pleasure.', 'YW55IGNhcm5hbCBwbGVhc3VyZS4=' )
test( 'any carnal pleasure', 'YW55IGNhcm5hbCBwbGVhc3VyZQ==' )
test( 'any carnal pleasur', 'YW55IGNhcm5hbCBwbGVhc3Vy' )
test( 'Man is distinguished, not only by his reason, but by this singular passion from other animals, which is a ' ..
	'lust of the mind, that by a perseverance of delight in the continued and indefatigable generation of knowledge, ' ..
	'exceeds the short vehemence of any carnal pleasure.', 'TWFuIGlzIGRpc3Rpbmd1aXNoZWQsIG5vdCBvbmx5IGJ5IGhpcyByZWFzb' ..
	'24sIGJ1dCBieSB0aGlzIHNpbmd1bGFyIHBhc3Npb24gZnJvbSBvdGhlciBhbmltYWxzLCB3aGljaCBpcyBhIGx1c3Qgb2YgdGhlIG1pbmQsIHRoY' ..
	'XQgYnkgYSBwZXJzZXZlcmFuY2Ugb2YgZGVsaWdodCBpbiB0aGUgY29udGludWVkIGFuZCBpbmRlZmF0aWdhYmxlIGdlbmVyYXRpb24gb2Yga25vd' ..
	'2xlZGdlLCBleGNlZWRzIHRoZSBzaG9ydCB2ZWhlbWVuY2Ugb2YgYW55IGNhcm5hbCBwbGVhc3VyZS4=' )
test( 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et ' ..
	'dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea ' ..
	'commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat ' ..
	'nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit ' ..
	'anim id est laborum.', 'TG9yZW0gaXBzdW0gZG9sb3Igc2l0IGFtZXQsIGNvbnNlY3RldHVyIGFkaXBpc2NpbmcgZWxpdCwgc2VkIGRvIGVp' ..
	'dXNtb2QgdGVtcG9yIGluY2lkaWR1bnQgdXQgbGFib3JlIGV0IGRvbG9yZSBtYWduYSBhbGlxdWEuIFV0IGVuaW0gYWQgbWluaW0gdmVuaWFtLCBx' ..
	'dWlzIG5vc3RydWQgZXhlcmNpdGF0aW9uIHVsbGFtY28gbGFib3JpcyBuaXNpIHV0IGFsaXF1aXAgZXggZWEgY29tbW9kbyBjb25zZXF1YXQuIER1' ..
	'aXMgYXV0ZSBpcnVyZSBkb2xvciBpbiByZXByZWhlbmRlcml0IGluIHZvbHVwdGF0ZSB2ZWxpdCBlc3NlIGNpbGx1bSBkb2xvcmUgZXUgZnVnaWF0' ..
	'IG51bGxhIHBhcmlhdHVyLiBFeGNlcHRldXIgc2ludCBvY2NhZWNhdCBjdXBpZGF0YXQgbm9uIHByb2lkZW50LCBzdW50IGluIGN1bHBhIHF1aSBv' ..
	'ZmZpY2lhIGRlc2VydW50IG1vbGxpdCBhbmltIGlkIGVzdCBsYWJvcnVtLg==')
test( '«В чащах юга жил бы цитрус? Да, но фальшивый экземпляр!»',
	'wqvQkiDRh9Cw0YnQsNGFINGO0LPQsCDQttC40Lsg0LHRiyDR' ..
	'htC40YLRgNGD0YE/INCU0LAsINC90L4g0YTQsNC70YzRiNC40LLRi9C5INGN0LrQt9C10LzQv9C70Y/RgCHCuw==')
test( '«В чащах юга жил бы цитрус? Да, фальшивый экземпляр!»',
	'wqvQkiDRh9Cw0YnQsNGFINGO0LPQsCDQttC40Lsg0LHRiyDRhtC' ..
	'40YLRgNGD0YE/INCU0LAsINGE0LDQu9GM0YjQuNCy0YvQuSDRjdC60LfQtdC80L/Qu9GP0YAhwrs=')
test( '\137\080\078\071\013\010\026\010\000\000\000\013\073\072\068\082\000\000\000\032\000\000\000\032\001\003\000' ..
	'\000\000\073\180\232\183\000\000\000\006\080\076\084\069\255\255\255\000\000\000\085\194\211\126\000\000\000\018' ..
	'\073\068\065\084\008\215\099\248\015\004\196\016\084\006\196\218\011\000\237\189\063\193\243\000\141\059\000\000' ..
	'\000\000\073\069\078\068\174\066\096\130', 'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgAQMAAABJtOi3AAAABlBMVEX///8AAABVwtN+' ..
	'AAAAEklEQVQI12P4DwTEEFQGxNoLAO29P8HzAI07AAAAAElFTkSuQmCC' )

assert( base64.decode('YW55IGNhcm5hbCBwbGVhc3VyZS4=\n\r\\' ) == 'any carnal pleasure.' )

assert( base64.decode('wйqеvнQсуkкiеDнRгhш9щCзwх0ъфYыnвQаsпNрGоFллIдNжGэOё0яLчPQsCDQttC40Lsg0LHRiyDRhtC' ..
	'40YLRgNGD0YE/INсCмUи0тLьAбsюIЙКNЕG\n\n\n\n\r\rE0LDQu9GM0YjQuNCy0YvQuSDRjdC60LfQtdC80L/Qu9GP0YAhwrs=') ==
	'«В чащах юга жил бы цитрус? Да, фальшивый экземпляр!»' )
