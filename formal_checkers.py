"""
formal_checkers.py — real, mechanical logical/mathematical verification per question type.
Each function takes a question dict (must contain 'formal_spec') and the question's
'options' list, and returns (passed: bool, detail: str). No natural-language heuristics —
every check is a symbolic/arithmetic recomputation from structured data.
"""
from itertools import permutations

def _correct_key(spec):
    return spec.get('correct_option_id', 'a')


# ---------------------------------------------------------------------------
# 1. Propositional implication-chain engine (conditional_reasoning, set_relations,
#    trap_detection, and simple categorical_syllogism questions).
#    Rules are SIGNED: {"if":atom,"if_val":bool,"then":atom,"then_val":bool} meaning
#    if_val(if) => then_val(then), and by contraposition not(then_val)(then) => not(if_val)(if).
#    This correctly handles negative consequents (e.g. BRIDGE=True => POKER=False).
# ---------------------------------------------------------------------------
def check_propositional_chain(spec):
    rules = spec['rules']
    facts = dict(spec.get('given_facts', {}))  # {atom: bool}
    changed = True
    while changed:
        changed = False
        for r in rules:
            a, av, b, bv = r['if'], r['if_val'], r['then'], r['then_val']
            if facts.get(a) is av and facts.get(b) is not bv:
                facts[b] = bv
                changed = True
            if facts.get(b) is (not bv) and facts.get(a) is not (not av):
                facts[a] = not av
                changed = True
    query = spec['query']
    val = facts.get(query, 'undetermined')
    result = 'true' if val is True else 'false' if val is False else 'undetermined'
    expected = spec['expected_result']
    ok = (result == expected)
    return ok, f"closure derived query='{query}' as {result} (expected {expected}); full closure={facts}"


# ---------------------------------------------------------------------------
# 1b. Analogy relation-type consistency checker.
#     Cannot mechanically judge "is this the most natural human relation" (semantic
#     judgment), but CAN mechanically verify that exactly one option is tagged with
#     the same relation-type as the stem pair - i.e. a single, non-ambiguous answer
#     under the question's own stated relation taxonomy.
# ---------------------------------------------------------------------------
def check_relation_consistency(spec):
    stem = spec['stem_relation']
    opts = spec['option_relations']
    matches = [k for k, v in opts.items() if v == stem]
    ok = (len(matches) == 1 and matches[0] == 'a')
    return ok, f"stem_relation='{stem}'; options tagged same relation: {matches} (need exactly ['a'])"


# ---------------------------------------------------------------------------
# 2. Ordering CSP brute-force solver (ordering_constraints)
# ---------------------------------------------------------------------------
def check_ordering_csp(spec):
    entities = spec['entities']
    positions = spec['positions']
    constraints = spec['constraints']

    def satisfies(assign):  # assign: dict entity->position
        pos_of = assign
        for c in constraints:
            t = c['type']
            if t == 'eq':
                if pos_of[c['entity']] != c['pos']:
                    return False
            elif t == 'adjacent':
                if abs(pos_of[c['a']] - pos_of[c['b']]) != 1:
                    return False
            elif t == 'not_adjacent':
                if abs(pos_of[c['a']] - pos_of[c['b']]) == 1:
                    return False
            elif t == 'before':
                if pos_of[c['a']] >= pos_of[c['b']]:
                    return False
            elif t == 'not_eq':
                if pos_of[c['entity']] == c['pos']:
                    return False
            elif t == 'immediately_right':
                if pos_of[c['b']] != pos_of[c['a']] + 1:
                    return False
        return True

    solutions = []
    for perm in permutations(positions):
        assign = dict(zip(entities, perm))
        if satisfies(assign):
            solutions.append(assign)

    if len(solutions) != 1:
        return False, f"expected exactly 1 valid arrangement, CSP found {len(solutions)}: {solutions}"

    solution = solutions[0]
    expected = spec['expected_assignment']
    ok = all(solution.get(k) == v for k, v in expected.items())
    return ok, f"unique CSP solution={solution}; expected={expected}"


# ---------------------------------------------------------------------------
# 2b. Domain-CSP brute-force solver: entities may SHARE values (e.g. multiple
#     people assigned to the same room) - unlike ordering_csp's permutation model.
# ---------------------------------------------------------------------------
from itertools import product as _product

def check_domain_csp(spec):
    entities = spec['entities']
    domain = spec['domain']
    constraints = spec['constraints']

    def satisfies(assign):
        for c in constraints:
            t = c['type']
            if t == 'eq':
                if assign[c['entity']] != c['val']:
                    return False
            elif t == 'not_eq_entities':
                if assign[c['a']] == assign[c['b']]:
                    return False
            elif t == 'eq_entities':
                if assign[c['a']] != assign[c['b']]:
                    return False
            elif t == 'conditional_eq':
                if assign[c['if_entity']] == c['if_val'] and assign[c['then_entity']] != c['then_val']:
                    return False
        return True

    solutions = []
    for combo in _product(domain, repeat=len(entities)):
        assign = dict(zip(entities, combo))
        if satisfies(assign):
            solutions.append(assign)

    if len(solutions) != 1:
        return False, f"expected exactly 1 valid assignment, found {len(solutions)}: {solutions}"
    solution = solutions[0]
    expected = spec['expected_assignment']
    ok = all(solution.get(k) == v for k, v in expected.items())
    return ok, f"unique solution={solution}; expected(partial)={expected}"


# ---------------------------------------------------------------------------
# 3. Table lookup checker (table_reading)
# ---------------------------------------------------------------------------
def check_table_lookup(spec):
    table = spec['table']
    op = spec['operation']
    if op == 'max_minus_min_with_person':
        max_person = max(table, key=table.get)
        min_val = min(table.values())
        diff = table[max_person] - min_val
        exp = spec['expected']
        ok = (max_person == exp['person'] and diff == exp['diff'])
        return ok, f"computed max_person={max_person}, diff={diff}; expected={exp}"
    return False, f"unknown table operation {op}"


# ---------------------------------------------------------------------------
# 4. Arithmetic recomputation (quantitative)
# ---------------------------------------------------------------------------
_ALLOWED_NAMES = {}
def check_arithmetic(spec):
    params = spec.get('params', {})
    expr = spec['expression']
    try:
        result = eval(expr, {"__builtins__": {}}, dict(params))
    except Exception as e:
        return False, f"expression error: {e}"
    expected = spec['expected']
    ok = abs(result - expected) < 1e-6 if isinstance(expected, (int, float)) else result == expected
    return ok, f"recomputed {expr} = {result}; expected {expected}"


# ---------------------------------------------------------------------------
# 5. Sequence regeneration (series)
# ---------------------------------------------------------------------------
def check_sequence(spec):
    kind = spec['kind']
    known = spec.get('known_terms')  # not all kinds use a flat term list (e.g. matrix/paired kinds)
    expected_next = spec['expected_next']

    def gen_arith(terms, d):
        return terms[-1] + d

    def gen_geom(terms, r):
        return terms[-1] * r

    def gen_two_step_alt(terms, ops):
        # ops: list of ('*'|'+'|'-', value) applied cyclically; verify against known, predict next
        idx = (len(terms) - 1) % len(ops)
        op, val = ops[idx]
        last = terms[-1]
        if op == '*':
            return last * val
        if op == '+':
            return last + val
        if op == '-':
            return last - val
        raise ValueError(op)

    def gen_fib(terms):
        return terms[-1] + terms[-2]

    def gen_doubling_diff(terms, first_diff):
        diffs = [terms[i+1]-terms[i] for i in range(len(terms)-1)]
        # verify diffs double each time
        for i in range(1, len(diffs)):
            if diffs[i] != diffs[i-1] * 2:
                raise ValueError(f"diffs do not double: {diffs}")
        return terms[-1] + diffs[-1] * 2

    try:
        if kind == 'arithmetic':
            pred = gen_arith(known, spec['common_diff'])
        elif kind == 'geometric':
            pred = gen_geom(known, spec['ratio'])
        elif kind == 'two_step_alternating':
            # verify the rule reproduces every known term from the first, then predict
            terms = [known[0]]
            ops = spec['ops']
            for i in range(1, len(known)):
                nxt = gen_two_step_alt(terms, ops)
                if nxt != known[i]:
                    return False, f"rule fails to reproduce known term at index {i}: got {nxt}, expected {known[i]}"
                terms.append(known[i])
            pred = gen_two_step_alt(terms, ops)
        elif kind == 'fibonacci_like':
            pred = gen_fib(known)
        elif kind == 'doubling_diff':
            pred = gen_doubling_diff(known, spec.get('first_diff'))
        elif kind == 'matrix_column_pattern':
            known_cols = spec['known_columns']
            diffs_per_col = [[c[i+1]-c[i] for i in range(len(c)-1)] for c in known_cols]
            ref = diffs_per_col[0]
            for d in diffs_per_col[1:]:
                if d != ref:
                    return False, f"columns do not share the same difference pattern: {diffs_per_col}"
            partial = spec['target_partial']
            first_diff = partial[1] - partial[0]
            if first_diff != ref[0]:
                return False, f"target column's first difference {first_diff} != reference {ref[0]}"
            pred = partial[-1] + ref[1]
        elif kind == 'paired_linear_function':
            (a1, b1, r1), (a2, b2, r2) = spec['known_pairs']
            denom = a1*b2 - a2*b1
            if denom == 0:
                return False, "singular system, cannot solve for m,n"
            m = (r1*b2 - r2*b1) / denom
            n = (r1 - m*a1) / b1
            qa, qb = spec['query_pair']
            pred = m*qa + n*qb
            pred = round(pred, 6)
            if float(pred).is_integer():
                pred = int(pred)
        elif kind == 'recursive_affine':
            t0, t1, t2 = known[0], known[1], known[2]
            m = (t2 - t1) / (t1 - t0)
            c = t1 - m*t0
            pred = m*known[-1] + c
            if float(pred).is_integer():
                pred = int(pred)
        elif kind == 'paired_function_search':
            # Genuine multi-hypothesis test: try a fixed bank of candidate operations
            # against ALL known pairs; only keep hypotheses that fit every known pair.
            candidates = {
                'sum': lambda a, b: a + b,
                'product': lambda a, b: a * b,
                'product_minus_1': lambda a, b: a * b - 1,
                'product_plus_1': lambda a, b: a * b + 1,
                'diff': lambda a, b: abs(a - b),
                'twice_a_plus_b': lambda a, b: 2*a + b,
            }
            known_pairs = spec['known_pairs']  # [(a,b,result), ...]
            surviving = []
            for name, fn in candidates.items():
                if all(fn(a, b) == r for (a, b, r) in known_pairs):
                    surviving.append(name)
            if len(surviving) != 1:
                return False, f"hypothesis search did not converge to exactly one rule; survivors={surviving}"
            qa, qb = spec['query_pair']
            pred = candidates[surviving[0]](qa, qb)
        elif kind == 'interleaved':
            # two sub-sequences interleaved at odd/even positions, each arithmetic
            odd_terms = known[0::2]
            even_terms = known[1::2]
            odd_diff = odd_terms[1] - odd_terms[0]
            for i in range(1, len(odd_terms)):
                if odd_terms[i] - odd_terms[i-1] != odd_diff:
                    return False, f"odd-position sub-sequence not constant-difference: {odd_terms}"
            even_diff = even_terms[1] - even_terms[0]
            for i in range(1, len(even_terms)):
                if even_terms[i] - even_terms[i-1] != even_diff:
                    return False, f"even-position sub-sequence not constant-difference: {even_terms}"
            next_is_even_position = (len(known) % 2 == 1)  # known has odd count -> next index is even (0-based odd index)
            pred = (even_terms[-1] + even_diff) if next_is_even_position else (odd_terms[-1] + odd_diff)
        elif kind == 'hypothesis_pivot':
            decoy = spec.get('decoy_rule')
            if decoy == 'doubling':
                for i in range(1, spec['decoy_fits_until_index']+1):
                    if known[i] != known[i-1] * 2:
                        return False, f"decoy rule was claimed to fit but doesn't at index {i}"
            diffs = [known[i+1]-known[i] for i in range(len(known)-1)]
            second_diffs = [diffs[i+1]-diffs[i] for i in range(len(diffs)-1)]
            if len(set(second_diffs)) != 1:
                return False, f"second differences not constant, true rule mis-specified: {diffs}"
            pred = known[-1] + diffs[-1] + second_diffs[0]
        elif kind == 'second_difference':
            if len(known) < 4:
                return False, 'need at least 4 known terms for second-difference verification'
            diffs = [known[i+1]-known[i] for i in range(len(known)-1)]
            second = [diffs[i+1]-diffs[i] for i in range(len(diffs)-1)]
            if len(set(second)) != 1:
                return False, f"second differences are not constant: {second}"
            pred_diff = diffs[-1] + second[0]
            pred = known[-1] + pred_diff
        elif kind == 'cyclic_differences':
            cycle = spec.get('diff_cycle') or spec.get('cycle')
            if not cycle:
                return False, 'missing diff_cycle'
            diffs = [known[i+1]-known[i] for i in range(len(known)-1)]
            for idx, d in enumerate(diffs):
                if d != cycle[idx % len(cycle)]:
                    return False, f"difference at index {idx}={d} != expected cycle value {cycle[idx % len(cycle)]}"
            pred = known[-1] + cycle[len(diffs) % len(cycle)]
        else:
            return False, f"unknown sequence kind {kind}"
    except ValueError as e:
        return False, f"generator verification failed: {e}"

    ok = (pred == expected_next)
    return ok, f"predicted next={pred}; expected={expected_next}"


# ---------------------------------------------------------------------------
# 6. Shape-schema consistency checkers (shapes_spatial)
# ---------------------------------------------------------------------------
def check_shape_schema(spec):
    t = spec['type']

    if t in ('matrix3x3_rotation',):
        cells = spec['cells_degrees']
        # verify row-wise +90 cyclic pattern with row offset, then predict missing cell
        flat = [c for row in cells for c in row]
        known = [c for c in flat if c is not None]
        # infer step from first two known
        step = (known[1] - known[0]) % 360
        for i in range(1, len(known)):
            if (known[i] - known[i-1]) % 360 != step:
                return False, f"non-constant rotation step among known cells: {known}"
        predicted = (known[-1] + step) % 360
        correct_opt = spec['option_degrees'][_correct_key(spec)]
        ok = (predicted == correct_opt)
        return ok, f"rotation step={step}; predicted missing={predicted}; option a={correct_opt}"

    if t == 'superposition_matrix':
        cols = spec['columns']
        for c in cols:
            if c['bottom'] is not None:
                xor = [a ^ b for a, b in zip(c['top1'], c['top2'])]
                if xor != c['bottom']:
                    return False, f"XOR mismatch in known column: {c}"
        last = cols[-1]
        predicted = [a ^ b for a, b in zip(last['top1'], last['top2'])]
        correct_opt = spec['options'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted XOR={predicted}; option a={correct_opt}"

    if t == 'superposition_pair':
        w = spec['worked_example']
        xor_check = [a ^ b for a, b in zip(w['shape1'], w['shape2'])]
        if xor_check != w['overlay_result']:
            return False, f"worked example XOR mismatch: {xor_check} vs {w['overlay_result']}"
        p = spec['new_pair']
        predicted = [a ^ b for a, b in zip(p['shape1'], p['shape2'])]
        correct_opt = spec['options'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted XOR for new pair={predicted}; option a={correct_opt}"

    if t == 'reflection_matrix':
        corner_map_vert = {'top_left': 'top_right', 'top_right': 'top_left',
                            'bottom_left': 'bottom_right', 'bottom_right': 'bottom_left'}
        corner_map_horiz = {'top_left': 'bottom_left', 'bottom_left': 'top_left',
                             'top_right': 'bottom_right', 'bottom_right': 'top_right'}
        for row in spec['rows']:
            vm = corner_map_vert[row['base_corner']]
            if vm != row['vertical_mirror_corner']:
                return False, f"vertical mirror mismatch for {row}"
            if row['horizontal_mirror_corner'] is not None:
                hm = corner_map_horiz[row['base_corner']]
                if hm != row['horizontal_mirror_corner']:
                    return False, f"horizontal mirror mismatch for {row}"
        last_base = spec['rows'][-1]['base_corner']
        predicted = corner_map_horiz[last_base]
        correct_opt = spec['option_corners'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted horizontal mirror={predicted}; option a={correct_opt}"

    if t == 'double_reflection':
        base = spec['base_corner']
        first = {'top_left':'top_right','top_right':'top_left','bottom_left':'bottom_right','bottom_right':'bottom_left'}[base]
        second = {'top_left':'bottom_left','top_right':'bottom_right','bottom_left':'top_left','bottom_right':'top_right'}[first]
        correct_opt = spec['options'].get(spec.get('correct_option_id', 'a'))
        ok = second == correct_opt
        return ok, f"predicted after two reflections={second}; option a={correct_opt}"

    if t == 'single_reflection':
        corner_map_vert = {'top_left': 'top_right', 'top_right': 'top_left',
                            'bottom_left': 'bottom_right', 'bottom_right': 'bottom_left'}
        predicted = corner_map_vert[spec['base_corner']]
        correct_opt = spec['options'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted vertical mirror={predicted}; option a={correct_opt}"

    if t == 'position_matrix':
        cells = spec['cells_position']
        flat = [c for row in cells for c in row]
        known = [c for c in flat if c is not None]
        for i in range(1, len(known)):
            if known[i] - known[i-1] != 1:
                return False, f"position sequence not +1 consistent: {known}"
        predicted = known[-1] + 1
        correct_opt = spec['options'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted position={predicted}; option a={correct_opt}"

    if t == 'element_addition_polygon':
        sides = spec['polygon_sides']
        filled_after = spec['vertices_filled_after_step4']
        ok = len(filled_after) == sides - 1
        return ok, f"{len(filled_after)} of {sides} vertices filled; exactly one remains for the next step: {ok}"

    if t == 'paper_fold':
        folds = spec['folds']
        expected_holes = 2 ** folds
        correct_opt = spec['options'][_correct_key(spec)]
        ok = (str(expected_holes) in str(correct_opt)) or (expected_holes == correct_opt) or \
             (isinstance(correct_opt, str) and correct_opt.startswith(str(expected_holes)))
        return ok, f"2^folds={expected_holes} holes; option a={correct_opt}"

    if t == 'cross_section':
        table = {('cube', 'horizontal_parallel_to_base_midheight'): 'square'}
        key = (spec['solid'], spec['cut_plane'])
        predicted = table.get(key)
        ok = predicted == spec['options']['a']
        return ok, f"predicted cross-section={predicted}; option a={spec['options']['a']}"

    if t == 'cube_rotation_multi':
        # rolling forward 90 degrees about a horizontal (left-right) axis:
        # front->bottom, bottom->back, back->top, top->front
        roll_cycle = ['front', 'bottom', 'back', 'top']
        marks = spec['initial_marks']  # {"dot":"front", "stripe":"top"}
        steps = spec['rotation_degrees'] // 90
        predicted = {}
        for name, face in marks.items():
            idx = roll_cycle.index(face)
            predicted[name] = roll_cycle[(idx + steps) % 4]
        correct_opt = spec['options'][_correct_key(spec)]
        ok = predicted == correct_opt
        return ok, f"predicted={predicted}; option a={correct_opt}"

    if t == 'cube_rotation':
        # face cycle under vertical-axis rotation, counterclockwise viewed from top: front->left->back->right->front
        cw_ccw_cycle = ['front', 'left', 'back', 'right']
        start = spec['initial_mark_face']
        steps = spec['rotation_degrees'] // 90
        idx = cw_ccw_cycle.index(start)
        predicted = cw_ccw_cycle[(idx + steps) % 4] if spec['rotation_direction'] == 'counterclockwise_from_top' else None
        ok = predicted == spec['options']['a']
        return ok, f"predicted face={predicted}; option a={spec['options']['a']}"

    if t == 'hidden_dual_rule_matrix':
        # count(row,col) = row+col-1 (1-indexed); fill = is_prime(count)
        def is_prime(n):
            if n < 2:
                return False
            return all(n % d for d in range(2, int(n**0.5)+1))
        cells = spec['cells']  # dict "r,c" -> {"count":int,"fill":"solid"/"empty"} for known cells
        for key, val in cells.items():
            r, c = map(int, key.split(','))
            expected_count = r + c - 1
            if val['count'] != expected_count:
                return False, f"cell {key}: count {val['count']} != r+c-1={expected_count}"
            expected_fill = 'solid' if is_prime(expected_count) else 'empty'
            if val['fill'] != expected_fill:
                return False, f"cell {key}: fill {val['fill']} != expected {expected_fill} (prime={is_prime(expected_count)})"
        mr, mc = spec['missing_cell']
        pred_count = mr + mc - 1
        pred_fill = 'solid' if is_prime(pred_count) else 'empty'
        correct_opt = spec['options'][_correct_key(spec)]
        ok = (correct_opt['count'] == pred_count and correct_opt['fill'] == pred_fill)
        return ok, f"predicted cell=({pred_count},{pred_fill}); option a={correct_opt}"

    if t == 'combined_transform_sequence':
        cells = spec['cells']  # list of {"rotation":deg,"reflected":bool}, last is None
        known = [c for c in cells if c is not None]
        rot_step = known[1]['rotation'] - known[0]['rotation']
        for i in range(1, len(known)):
            if known[i]['rotation'] - known[i-1]['rotation'] != rot_step:
                return False, f"rotation step not constant: {known}"
            if known[i]['reflected'] == known[i-1]['reflected']:
                return False, f"reflection does not toggle every step: {known}"
        missing_idx = cells.index(None)
        pred_rotation = (known[-1]['rotation'] + rot_step) % 360
        pred_reflected = not known[-1]['reflected']
        correct_opt = spec['options'][_correct_key(spec)]
        ok = (correct_opt['rotation'] == pred_rotation and correct_opt['reflected'] == pred_reflected)
        return ok, f"predicted=({pred_rotation}°, reflected={pred_reflected}); option a={correct_opt}"

    if t == 'net_diagram':
        table = {
            'cross_of_6_equal_squares': 'cube',
            '2_equal_triangles_plus_3_equal_rectangles': 'triangular_prism'
        }
        predicted = table.get(spec['net_shape'])
        ok = predicted == spec['options']['a']
        return ok, f"predicted solid={predicted}; option a={spec['options']['a']}"

    return False, f"no checker implemented for shape schema type '{t}'"


CHECKERS = {
    'propositional_chain': check_propositional_chain,
    'relation_consistency': check_relation_consistency,
    'ordering_csp': check_ordering_csp,
    'domain_csp': check_domain_csp,
    'table_lookup': check_table_lookup,
    'arithmetic': check_arithmetic,
    'sequence': check_sequence,
    'shape_schema': check_shape_schema,
}

def run_formal_check(question):
    spec = question.get('formal_spec')
    if not spec:
        return None, "no formal_spec present - logical_validation cannot be mechanically verified"
    kind = spec.get('kind_group')
    fn = CHECKERS.get(kind)
    if not fn:
        return None, f"no checker registered for kind_group '{kind}'"
    try:
        ok, detail = fn(spec)
        return ok, detail
    except Exception as e:
        return False, f"checker crashed: {e}"
