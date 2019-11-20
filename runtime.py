from utils import missing
from nodes import EvalContext
from exceptions import UndefinedError

def resolve_or_missing(context, key, missing=missing):
    if key in context.vars:
        return context.vars[key]
    if key in context.parent:
        return context.parent[key]
    return missing


class Context:
    def __init__(self, environment, parent, name, blocks):
        self.parent = parent
        self.vars = {}
        self.environment = environment
        self.eval_ctx = EvalContext(self.environment, name)
        self.name = name
        self.blocks = dict(blocks)
    
    def __contains__(self, name):
        return name in self.vars or name in self.parent
    
    def __getitem__(self, key):
        item = self.resolve_or_missing(key)
        if item is missing:
            raise KeyError(key)
        return item

    def resolve(self, key):
        rv = resolve_or_missing(self, key)
        if rv is missing:
            return self.environment.undefined(name=key)
        return rv

    def resolve_or_missing(self, key):
        rv = self.resolve(key)
        if isinstance(rv, Undefined):
            rv = missing
        return rv

    def get_all(self):
        if not self.vars:
            return self.parent
        if not self.parent:
            return self.vars
        return dict(self.parent, **self.vars)


def new_context(environment, template_name, blocks, vars=None):
    if vars is None:
        vars = {}
    parent = vars
    return Context(environment, parent, template_name, blocks)


class Undefined:
    def __init__(self, hint=None, obj=missing, name=None):
        self._undefined_hint = hint, 
        self._undefined_obj = obj
        self._undefined_name = name

    def __getattr__(self, name):
        return self.fail_with_undefined_error()
    
    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
        __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
        __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
        __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
        __float__ = __complex__ = __pow__ = __rpow__ = __sub__ = \
        __rsub__ = fail_with_undefined_error
    
    def __eq__(self, other):
        return type(self) is type(other)
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def fail_with_undefined_error(self, *args, **kwargs):
        if not self._undefined_hint:
            if self._undefined_name:
                hint = '%r is undefined' % self._undefined_name
            else:
                hint = ''
                # TODO: write something here
        else:
            hint = self._undefined_hint
        raise UndefinedError(hint)
