# -*- coding: utf-8 -*-

# Copyright 2018 Orange
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Tests for datalog_unfolding module"""

import z3

from octant.common import ast
from octant.common import primitives
from octant.datalog import origin
from octant.datalog import unfolding
from octant.front import parser
from octant.source import source
from octant.tests import base


prog0 = """
    t(X, 1) :- p(X).
    t(X,2) :- p(X).
    s(X, 1) :- p(X).
    s(X, Y) :- q(X,Y).
    """

prog1 = """
    t(X, Y) :- s(X1, X2, Y2), p(X1), q(X2, Y2), r(X2),
               r(Y2), X1 = X & X2, Y2 = Y & 15.
    """

prog2 = """
    t(X, Y) :- p(X1), s(X2), X1 = X & X2.
    s(X) :- p(X).
    s(X) :- q(X).
    """


class TestUnfolding(base.TestCase):
    """Tests of utility functions"""

    def test_simplify_to_ground_types(self):
        t1 = origin.UFGround(1, "t", None)
        t2 = origin.UFGround(1, "t", None)
        t3 = origin.UFDisj((t1, t2))
        t4 = origin.UFConj((
            t1, origin.UFConj((t2, t1)),
            origin.UFBot(), t3))
        expected = [t1, t2, t1, t3]
        self.assertEqual(
            expected,
            origin.simplify_to_ground_types(t4))

    def test_len_occ(self):
        self.assertEqual(0, origin.len_occ(None))
        self.assertEqual(1, origin.len_occ(('m', None)))
        self.assertEqual(2, origin.len_occ(('n', ('m', None))))

    def test_weight_type(self):
        t1 = origin.UFGround(1, "t", ('m', None))
        t2 = origin.UFBot()
        t3 = origin.UFDisj((t1, t2))
        t4 = origin.UFConj((t1, t2, t1))
        self.assertEqual((0, 1), origin.weight_type(t1))
        self.assertEqual((2, 0), origin.weight_type(t2))
        self.assertEqual((1, 2), origin.weight_type(t3))
        self.assertEqual((1, 3), origin.weight_type(t4))

    def test_wrap_type(self):
        mark = 'm'
        t1 = origin.UFGround(1, "t", None)
        t2 = origin.UFGround(1, "t", ('n', None))
        t3 = origin.UFDisj((t1, t2))
        t4 = origin.UFConj((
            t1, origin.UFConj((t2, t1)),
            origin.UFBot(), t3))
        e1 = origin.UFGround(1, "t", (mark, None))
        e2 = origin.UFGround(1, "t", (mark, ('n', None)))
        e3 = origin.UFDisj((e1, e2))
        e4 = origin.UFConj((
            e1, origin.UFConj((e2, e1)),
            origin.UFBot(), e3))
        self.assertEqual(e4, origin.wrap_type(t4, mark))

    def test_reduce_disj(self):
        t1 = origin.UFGround(1, "t", None)
        t2 = origin.UFGround(2, "u", None)
        t3 = origin.UFBot()
        t4 = origin.UFDisj((t1, t2))
        t5 = origin.UFDisj((t1, t3))
        t6 = origin.UFDisj((t1, origin.top))
        result = origin.reduce_disj([t4, t1, t5])
        self.assertIsInstance(result, origin.UFDisj)
        self.assertEqual(3, len(result.args))
        self.assertEqual(origin.top, origin.reduce_disj([t4, t1, t6]))

    def test_reduce_conj(self):
        t1 = origin.UFGround(1, "t", None)
        t2 = origin.UFGround(2, "u", None)
        t3 = origin.UFGround(2, "v", None)
        t4 = origin.UFDisj((t1, t2))
        t5 = origin.UFDisj((t1, t3))
        result = origin.reduce_conj([t1, t2, t4, t5])
        self.assertIsInstance(result, origin.UFConj)
        self.assertEqual(set(result.args), {t1, t2})

    def test_get_to_solve(self):
        prog = parser.wrapped_parse("t(X) :- p(X,Y), X = Y & 1, q(X), X < 10.")
        rule = prog[0]
        vars = rule.body_variables()
        # Only the first is to solve. There is only one variable in the
        # equality.
        expected = [(vars, 1)]
        self.assertEqual(expected, unfolding.get_to_solve(prog[0]))

    def test_candidates(self):
        v1, v2, v3 = (('X', 0), ('Y', 0), ('Z', 0))
        problems = [({v1, v2}, 1), ({v1, v3}, 2), ({v1}, 3)]
        self.assertEqual({v1, v2, v3}, unfolding.candidates(problems))

    def test_unfolding(self):
        prog = "t(X) :- p(X,Y), X = Y & 1.\ns(X) :- t(X), 2 = X & 2."
        rules = parser.wrapped_parse(prog)
        extensible = {"p": ["int", "int"]}
        unfold = origin.Origin(rules, extensible)
        self.assertEqual((2, True), unfold.tables["p"])
        self.assertEqual((1, False), unfold.tables["t"])

    def test_partially_ground(self):
        rules = parser.wrapped_parse(prog0)
        unfold = origin.Origin(rules, {})
        result = unfold.get_partially_ground_preds()
        self.assertEqual({'s': set(), 't': set([1])}, result)

    def test_initialize_types_and_get_atom_types(self):
        rules = parser.wrapped_parse(prog0)
        atom_t = rules[0].head
        atom_z = ast.Atom('z', [])
        external = {'q': ['int', 'int'], 'p': ['int']}
        unfold = origin.Origin(rules, external)
        unfold.initialize_types()
        self.assertEqual(
            [origin.UFBot(), origin.UFGround(1, "t", None)],
            unfold.table_types['t'])
        self.assertEqual(
            origin.UFBot(),
            unfold.get_atom_type(atom_t, 0))
        self.assertEqual(None, unfold.get_atom_type(atom_t, 3))
        self.assertEqual(None, unfold.get_atom_type(atom_z, 0))

    def test_type_variables(self):
        rules = parser.wrapped_parse(prog0)
        vars = [rules[rid].head.args[pos].full_id()
                for (rid, pos) in [(1, 0), (3, 0), (3, 1)]]
        external = {'q': ['int', 'int'], 'p': ['int']}
        unfold = origin.Origin(rules, external)
        unfold.initialize_types()
        unfold.type_variables()
        typs = [unfold.var_types[v] for v in vars]
        self.assertEqual(['p', 'q', 'q'], [t.table for t in typs])
        self.assertEqual([0, 0, 1], [t.pos for t in typs])
        occs = [t.occurrence for t in typs]
        self.assertEqual(occs[1], occs[2])
        self.assertEqual(False, occs[0] == occs[1])

    def test_type_tables(self):
        rules = parser.wrapped_parse(prog0)
        external = {'q': ['int', 'int'], 'p': ['int']}
        unfold = origin.Origin(rules, external)
        unfold.initialize_types()
        unfold.type_variables()
        result = unfold.type_tables()
        typ_s0 = result['s'][0]
        self.assertIsInstance(typ_s0, origin.UFDisj)

    def test_type(self):
        rules = parser.wrapped_parse(prog0)
        external = {'q': ['int', 'int'], 'p': ['int']}
        unfold = origin.Origin(rules, external)
        unfold.type()
        result = unfold.table_types
        typ_s0 = result['s'][0]
        self.assertIsInstance(typ_s0, origin.UFDisj)

    def test_strategy_1(self):
        rules = parser.wrapped_parse(prog1)
        external = {'q': ['int', 'int'], 'p': ['int'], 'r': ['int']}
        unfold = unfolding.Unfolding(rules, external, (lambda t: t))
        ogn = origin.Origin(rules, external)
        var_types = ogn.type()
        result = unfold.rule_strategy(var_types, rules[0])
        filtered = [(t, sorted(pos)) for (((t, pos),), _) in result]
        self.assertEqual([('q', [0, 1]), ('p', [0])], filtered)

    def test_strategy_2(self):
        rules = parser.wrapped_parse(prog2)
        rule = rules[0]
        external = {'q': ['int'], 'p': ['int']}
        unfold = unfolding.Unfolding(rules, external, (lambda t: t))
        ogn = origin.Origin(rules, external)
        var_types = ogn.type()
        result = unfold.rule_strategy(var_types, rule)
        filtered = [
            sorted([(t, sorted(pos)) for (t, pos) in plan],
                   key=lambda p: p[0])
            for (plan, _) in result]
        self.assertEqual([[('p', [0])], [('p', [0]), ('q', [0])]], filtered)

    def test_plan_to_program(self):
        rules = parser.wrapped_parse(prog0)   # arbitrary not really used
        rules[0].id = 0         # but we need a zero rule
        fp = z3.Fixedpoint()
        datasource = source.Datasource(primitives.TYPES)
        octant_type = datasource.types["int4"]
        z3_type = octant_type.type()

        def mkv(v):
            return z3.BitVecVal(v, z3_type)

        p = z3.Function('p', z3_type, z3_type, z3.BoolSort())
        q = z3.Function('q', z3_type, z3_type, z3.BoolSort())
        for (x, y) in [(3, 0), (4, 1)]:
            fp.add_rule(p(mkv(x), mkv(y)))
        for (x, y) in [(5, 0), (6, 1)]:
            fp.add_rule(q(mkv(x), mkv(y)))
        relations = {'p': p, 'q': q}
        x = ast.Variable("X", "int4")
        y = ast.Variable("Y", "int4")
        z = ast.Variable("Z", "int4")
        for f in [p, q]:
            fp.register_relation(f)
        unfold_plan = unfolding.UnfoldPlan(
            {0: [((('p', [1, 0]),), [x, y]),
                 ((('q', [0, 1]),), [z, x])]},
            {})
        records = unfolding.plan_to_program(
            unfold_plan, fp, datasource, relations, rules)
        self.assertIn(0, records)
        trimmed = sorted([
            sorted((var, val.as_long()) for ((var, _), val) in rec.items())
            for rec in records[0]
        ], key=lambda t: t[0])
        expected = [
            [('X', 0), ('Y', 3), ('Z', 5)],
            [('X', 1), ('Y', 4), ('Z', 6)]
        ]
        self.assertEqual(expected, trimmed)

    def test_plan_to_program_idb(self):
        rules = parser.wrapped_parse(prog0)   # arbitrary not really used
        rules[0].id = 0
        fp = z3.Fixedpoint()
        datasource = source.Datasource(primitives.TYPES)
        octant_type = datasource.types["int4"]
        z3_type = octant_type.type()

        def mkv(v):
            return z3.BitVecVal(v, z3_type)

        p = z3.Function('p', z3_type, z3_type, z3.BoolSort())
        q = z3.Function('q', z3_type, z3_type, z3.BoolSort())
        content = {
            'p': [(mkv(3), mkv(0)), (mkv(4), mkv(1))]
        }
        for (x, y) in [(5, 0), (6, 1)]:
            fp.add_rule(q(mkv(x), mkv(y)))
        relations = {'p': p, 'q': q}
        x = ast.Variable("X", "int4")
        y = ast.Variable("Y", "int4")
        z = ast.Variable("Z", "int4")
        for f in [p, q]:
            fp.register_relation(f)
        unfold_plan = unfolding.UnfoldPlan(
            {0: [((('p', [1, 0]),), [x, y]),
                 ((('q', [0, 1]),), [z, x])]},
            content)
        records = unfolding.plan_to_program(
            unfold_plan, fp, datasource, relations, rules)
        self.assertIn(0, records)
        trimmed = sorted([
            sorted((var, val.as_long()) for ((var, _), val) in rec.items())
            for rec in records[0]
        ], key=lambda t: t[0])
        expected = [
            [('X', 0), ('Y', 3), ('Z', 5)],
            [('X', 1), ('Y', 4), ('Z', 6)]
        ]
        self.assertEqual(expected, trimmed)
