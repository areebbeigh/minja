class Node:
    attributes = ('lineno',)
    fields = ()
    
    def __init__(self, *fields, **attributes):
        assert len(fields) <= len(self.fields)

        for idx, field in enumerate(fields):
            setattr(self, self.fields[idx], field)

        for k, v in attributes.items():
            assert k in self.attributes
            setattr(self, k, v)
    
    def __repr__(self):
        rv = [self.__class__.__name__, '(']
        for idx, k in enumerate(self.fields):
            v = getattr(self, k)
            if isinstance(v, str):
                v = "'{}'".format(v.replace('\n', '\\n'))
            rv.append('{0}={1}'.format(k, v))
            if idx != len(self.fields) - 1:
                rv.append(', ')
        rv.append(')')
        return ''.join(rv)


class Partial(Node):
    """Nodes that make sense only in conjuction with a complete node"""

class Template(Node):
    fields = ('body',)

class Output(Node):
    fields = ('body',)

class Stmt(Node):
    pass

class Extends(Stmt):
    fields = ('template',)

class With(Stmt):
    fields = ('targets', 'values', 'body')

class If(Stmt):
    fields = ('test', 'body', 'elif_', 'else_')

class For(Stmt):
    fields = ('target', 'iter', 'body', 'else_')

class Block(Stmt):
    fields = ('name', 'body')

class Expr(Node):
    pass

class Literal(Expr):
    pass

class TemplateData(Literal):
    fields = ('body',)

class Const(Literal):
    fields = ('value',)

class Tuple(Literal):
    fields = ('items',)

class List(Literal):
    fields = ('items',)

class Pair(Partial):
    fields = ('key', 'value')

class Dict(Literal):
    """Items are of type `Pair`"""
    fields = ('items',)

class Name(Expr):
    fields = ('name',)

class Call(Expr):
    fields = ('node', 'args', 'kwargs', 'dyn_args', 'dyn_kwargs')

class Keyword(Partial):
    fields = ('key', 'value')

class Getattr(Expr):
    fields = ('node', 'attr')

class Getitem(Expr):
    fields = ('node', 'attr')

class Slice(Expr):
    fields = ('start', 'stop', 'step')

class Compare(Expr):
    fields = ('expr', 'operands')

class Operand(Partial):
    fields = ('operator', 'expr')

class BinExpr(Expr):
    fields = ('left', 'right')
    operator = None

class UnaryExpr(Expr):
    fields = ('node',)

class Add(BinExpr):
    operator = '+'

class Sub(BinExpr):
    operator = '-'

class Mul(BinExpr):
    operator = '+'

class Div(BinExpr):
    operator = '/'

class FloorDiv(BinExpr):
    operator = '//'

class Mod(BinExpr):
    operator = '%'

class Pow(BinExpr):
    operator = '**'

class And(BinExpr):
    operator = 'and'

class Or(BinExpr):
    operator = 'or'

class Not(UnaryExpr):
    operator = 'not'

class Neg(UnaryExpr):
    operator = '-'

class Pos(UnaryExpr):
    operator = '+'
