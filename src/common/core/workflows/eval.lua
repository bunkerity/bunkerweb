-- Three-valued evaluator for compiled workflow condition trees.
--
-- Deliberately knows nothing about requests, GeoIP or NGINX: it walks combinators and
-- calls the leaf closures the plugin compiled at init. That seam is what makes the algebra
-- — the part that is easy to get subtly wrong — testable with a plain Lua interpreter.
--
-- Truth values are plain integers, so a whole evaluation allocates nothing: no table, no
-- string, no closure is created per request.
local F, T, U = 0, 1, 2

-- Combinators are integers too, for the same reason.
local ALL, ANY, NOT = 1, 2, 3

local NEGATE = { [F] = T, [T] = F, [U] = U }

local eval = { FALSE = F, TRUE = T, UNKNOWN = U, ALL = ALL, ANY = ANY, NOT = NOT }

-- A node is either a leaf `{ f = function(bw) -> F|T|U }` or a combinator
-- `{ op = ALL|ANY|NOT, [1] = child, [2] = child, ... }` (NOT takes exactly one child).
--
-- Short-circuiting is asymmetric and that asymmetry is the whole subtlety: ALL may return
-- early on FALSE and ANY on TRUE, but NEITHER may return early on UNKNOWN — a later FALSE
-- still settles an ALL, and a later TRUE still settles an ANY. Exiting early on UNKNOWN
-- would turn a knowable FALSE into an UNKNOWN, and an UNKNOWN rule never matches, so the
-- bug would silently disable rules instead of raising anything.
local function run(node, bw)
	local op = node.op
	if not op then
		return node.f(bw)
	end
	if op == NOT then
		return NEGATE[run(node[1], bw)]
	end
	local unknown = false
	for i = 1, #node do
		local result = run(node[i], bw)
		if op == ALL then
			if result == F then
				return F
			end
		elseif result == T then
			return T
		end
		if result == U then
			unknown = true
		end
	end
	if unknown then
		return U
	end
	-- Every child settled: an ALL with no FALSE is TRUE, an ANY with no TRUE is FALSE.
	return op == ALL and T or F
end

eval.run = run

return eval
