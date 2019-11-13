import operator
from collections import deque

_binop_to_func = {
    '*':        operator.mul,
    '/':        operator.truediv,
    '//':       operator.floordiv,
    '**':       operator.pow,
    '%':        operator.mod,
    '+':        operator.add,
    '-':        operator.sub
}

_uaop_to_func = {
    'not':      operator.not_,
    '+':        operator.pos,
    '-':        operator.neg
}

_cmpop_to_func = {
    'eq':       operator.eq,
    'ne':       operator.ne,
    'gt':       operator.gt,
    'gteq':     operator.ge,
    'lt':       operator.lt,
    'lteq':     operator.le,
    'in':       lambda a, b: a in b,
    'notin':    lambda a, b: a not in b
}


class Impossible(Exception): pass


class EvalContext:
    def __init__(self, environment, template_name=None):
        self.environment = environment
        self.autoescape = environment.autoescape


def get_eval_ctx(node, ctx=None):
    if ctx is None:
        if not node.environment:
            raise RuntimeError('Need node to have environment attribute'
                            ' if no context is passed')
        return EvalContext(node.environment)
    return ctx


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

    def iter_fields(self, exclude=None, only=None):
        for name in self.fields:
            if (exclude is None and only is None or
                exclude is not None and name not in exclude or
                only is not None and name in only):
                try:
                    yield name, getattr(self, name)
                except AttributeError:
                    pass
    
    def iter_child_nodes(self, exclude=None, only=None):
        for field, item in self.iter_fields(exclude, only):
            if isinstance(item, list):
                for n in item:
                    if isinstance(n, Node):
                        yield n
            elif isinstance(item, Node):
                yield item
    
    def find(self, node_type):
        for result in self.find_all(node_type):
            return result
    
    def find_all(self, node_type):
        for ch in self.iter_child_nodes():
            if isinstance(ch, node_type):
                yield ch
            for result in ch.find_all(node_type):
                yield result
    
    def set_ctx(self, ctx):
        todo = deque([self])
        while todo:
            node = todo.popleft()
            if 'ctx' in node.fields:
                node.ctx = ctx
                todo.extend(node.iter_child_nodes())
        return self
    
    def as_const(self, eval_ctx=None):
        raise Impossible()

class Partial(Node):
    """Nodes that make sense only in conjuction with a complete node"""

class Template(Node):
    fields = ('body',)

class Output(Node):
    fields = ('nodes',)

class Stmt(Node):
    pass

class Extends(Stmt):
    fields = ('template',)

class With(Stmt):
    fields = ('targets', 'values', 'body')

class If(Stmt):
    fields = ('test', 'body', 'elif_', 'else_')

class For(Stmt):
    fields = ('target', 'iter', 'body', 'test', 'else_')

class Block(Stmt):
    fields = ('name', 'body')

class Expr(Node):
    def as_const(self, eval_ctx=None):
        raise Impossible()

class Literal(Expr):
    pass

class TemplateData(Literal):
    fields = ('body',)

    def as_const(self, eval_ctx=None):
        return self.body

class Const(Literal):
    fields = ('value',)

    def as_const(self, eval_ctx=None):
        return self.value

class Tuple(Literal):
    fields = ('items', 'ctx')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return tuple(x.as_const(eval_ctx) for x in self.items)

class List(Literal):
    fields = ('items',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return [x.as_const(eval_ctx) for x in self.items]

class Pair(Partial):
    fields = ('key', 'value')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return self.key.as_const(eval_ctx), self.value.as_const(eval_ctx)

class Dict(Literal):
    """Items are of type `Pair`"""
    fields = ('items',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return dict(x.as_const() for x in self.items)

class Name(Expr):
    fields = ('name', 'ctx')

class Call(Expr):
    fields = ('node', 'args', 'kwargs', 'dyn_args', 'dyn_kwargs')

class Keyword(Partial):
    fields = ('key', 'value')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return self.key, self.value.as_const()

class Getattr(Expr):
    fields = ('node', 'attr', 'ctx')

class Getitem(Expr):
    fields = ('node', 'attr', 'ctx')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        # TODO: inspect original
        

class Slice(Expr):
    fields = ('start', 'stop', 'step')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(eval_ctx)
        
        def const(x):
            return x if x is None else x.as_const(eval_ctx)

        return slice(const(self.start), const(self.stop), const(self.step))

class Compare(Expr):
    fields = ('expr', 'operands')

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(eval_ctx)
        result = val = self.expr.as_const(eval_ctx)
        try:
            for operand in self.operands:
                new_val = operand.expr.as_const(eval_ctx)
                result = _cmpop_to_func[operand.operator](val, new_val)
                if not result:
                    return False
                val = new_val
        except Exception:
            raise Impossible()
        return True

class Operand(Partial):
    fields = ('operator', 'expr')

class BinExpr(Expr):
    fields = ('left', 'right')
    operator = None

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        f = _binop_to_func[self.operator]
        try:
            f(self.left.as_const(eval_ctx), self.right.as_const(eval_ctx))
        except Exception:
            raise Impossible()

class UnaryExpr(Expr):
    fields = ('node',)

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        f = _uaop_to_func[self.operator]
        try:
            return f(self.node.as_const(eval_ctx))
        except Exception:
            raise Impossible()

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

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return self.left.as_const(eval_ctx) and self.right.as_const(eval_ctx)

class Or(BinExpr):
    operator = 'or'

    def as_const(self, eval_ctx=None):
        eval_ctx = get_eval_ctx(self, eval_ctx)
        return self.left.as_const(eval_ctx) or self.right.as_const(eval_ctx)

class Not(UnaryExpr):
    operator = 'not'

class Neg(UnaryExpr):
    operator = '-'

class Pos(UnaryExpr):
    operator = '+'
