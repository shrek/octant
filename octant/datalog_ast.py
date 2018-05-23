#    Copyright 2018 Orange
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""AST for Datalog"""


class AST(object):
    """Base ast (abstract syntax tree) type for octant Datalog"""

    def __ne__(self, other):
        return not self.__eq__(other)


class Rule(AST):
    """Represents a rule"""

    def __init__(self, head, body):
        self.head = head
        self.body = body

    def body_variables(self):
        """Body variables of a rule as a set."""
        return set(v for x in self.body for v in x.variables())

    def head_variables(self):
        """Head variables of a rule"""
        return set(self.head.variables())

    def head_table(self):
        """Table introduced by the rule"""
        return self.head.table

    def body_tables(self):
        """All tables used by the rule"""
        return set(atom.table for atom in self.body)

    def rename_variables(self, renaming):
        """Rename variables according to renaming"""
        self.head.rename_variables(renaming)
        for atom in self.body:
            atom.rename_variables(renaming)

    def __repr__(self):
        return "{} :- {}".format(self.head, self.body)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return other.head == self.head and other.body == self.body
        return False


class Atom(AST):
    """Represents an atom either in the head or body"""

    def __init__(self, table, args, negated=False, labels=None):
        self.table = table
        self.args = args
        self.negated = negated
        self.labels = labels

    def variables(self):
        """Variables of the atom"""
        return set(v for x in self.args for v in x.variables())

    def rename_variables(self, renaming):
        """Rename variables"""
        for arg in self.args:
            arg.rename_variables(renaming)

    def __repr__(self):
        return "{}{}({})".format(
            "~" if self.negated else "",
            self.table,
            (', '.join('{} = {}'.format(lab, val)
                       for (lab, val) in zip(self.labels, self.args))
             if self.labels is not None
             else ', '.join(str(val) for val in self.args)))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (other.table == self.table and other.args == self.args and
                    other.negated == self.negated and
                    other.labels == self.labels)
        return False


class Expr(AST):
    "An abstract expression with an optional"

    def __init__(self, type=None):
        self.type = type

    def variables(self):
        """Free variables (default is none)"""
        return set()

    def rename_variables(self, renaming):
        """Variable renaming (default is nothing)"""
        pass


class Variable(Expr):
    "A variable (scope rule)"

    def __init__(self, ident, type=None):
        super(Variable, self).__init__(type=type)
        self.id = ident

    def variables(self):
        return set([self.id])

    def __repr__(self):
        expr_repr = (
            self.id if self.type is None
            else "{}:{}".format(self.id, self.type))
        return expr_repr

    def rename_variables(self, renaming):
        if self.id in renaming:
            self.id = renaming[self.id]

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (other.id == self.id)
        return False


class Operation(Expr):
    "An n-ary operation"

    def __init__(self, oper, args, type=None):
        super(Operation, self).__init__(type=type)
        self.operation = oper
        self.args = args
        self.var_types = []  # type variable for polymorphic operators.

    def variables(self):
        return set(v for x in self.args for v in x.variables())

    def rename_variables(self, renaming):
        for arg in self.args:
            arg.rename_variables(renaming)

    def __repr__(self):
        return "{}({})".format(self.operation, self.args)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (other.operation == self.operation and
                    other.args == self.args)
        return False


class NumConstant(Expr):
    "A numeric constant"

    def __init__(self, val, type='int'):
        super(NumConstant, self).__init__(
            type=type)
        self.val = val

    def __repr__(self):
        return str(self.val)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (other.val == self.val and other.type == self.type)
        return False


class StringConstant(Expr):
    "A string constant"

    def __init__(self, val, type='string'):
        super(StringConstant, self).__init__(type=type)
        self.val = val

    def __repr__(self):
        return '"{}"'.format(self.val)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (other.val == self.val and other.type == self.type)
        return False


class BoolConstant(Expr):
    "A boolean constant"

    def __init__(self, val):
        super(BoolConstant, self).__init__(type='bool')
        self.val = val

    def __repr__(self):
        return str(self.val)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return other.val == self.val
        return False


class IpConstant(Expr):
    "An ip address constant"

    def __init__(self, val):
        super(IpConstant, self).__init__(type='ip_address')
        self.val = val

    def __repr__(self):
        return self.val

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return other.val == self.val
        return False


class TypedTable(object):
    """A table with a name and types of its columns"""
    def __init__(self, name, params=None):
        self.name = name
        self.params = params if params is not None else []

    def __str__(self):
        return "[{}({})]".format(
            self.name,
            ",".join(str(x) for x in self.params))


class Constant(AST):
    """A constant to be substituted"""
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return other.name == self.name
        return False
