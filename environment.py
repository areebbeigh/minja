import sys

from lexer import TemplateSyntaxError
from parser import Parser
from lexer import Lexer
from compiler import generate
from utils import concat
from runtime import new_context, Undefined


class Environment:
    def __init__(self, autoescape=False):
        self.autoescape = autoescape
        self.lexer = Lexer(self)
        self.undefined = Undefined

    def handle_exception(self, exc_info, source_hint=None):
        pass

    def getitem(self, obj, argument):
        try:
            return obj[argument]
        except (AttributeError, TypeError, LookupError):
            if isinstance(argument, str):
                try:
                    return getattr(obj, argument)
                except AttributeError:
                    pass
            return self.undefined(obj=obj, name=argument)
        
    def getattr(self, obj, attribute):
        try:
            return getattr(obj, attribute)
        except AttributeError:
            pass
        try:
            return obj[attribute]
        except(TypeError, LookupError, AttributeError):
            return self.undefined(obj=obj, name=attribute)

    def from_string(self, source):
        return Template.from_code(self, self.compile(source))
    
    def tokenize(self, source):
        return self.lexer.tokenize(source)

    def _parse(self, source, name, filename):
        return Parser(self, source).parse()

    def parse(self, source, name=None, filename=None):
        try:
            return self._parse(source, name, filename)
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        self.handle_exception(exc_info, source_hint=source)

    def _generate(self, node, name, filename):
        return generate(node, self, name)

    def compile(self, source, name=None, filename=None):
        source_hint = None
        try:
            if isinstance(source, str):
                source_hint = source
                source = self._parse(source, name, filename)
            source = self._generate(source, name, filename)
            with open('output.py', 'w') as f:
                f.write(source)
            if filename is None:
                filename = '<template>'
            rv = self._compile(source, filename)
            return rv
        except TemplateSyntaxError:
            exc_info = sys.exc_info()
        self.handle_exception(exc_info, source_hint=source_hint)

    def _compile(self, source, filename):
        return compile(source, filename, 'exec')


class Template:
    def __new__(cls, source, autoescape=False):
        env = Environment(autoescape)
        return env.from_string(source)
    
    @classmethod
    def from_code(cls, environment, code):
        namespace = {
            'environment': environment,
            '__file__': code.co_filename
        }
        exec(code, namespace)
        rv = cls._from_namespace(environment, namespace)
        return rv

    @classmethod
    def _from_namespace(cls, environment, namespace):
        t = object.__new__(cls)
        t.environment = environment
        t.name = namespace['name']
        t.filename = namespace['__file__']
        t.blocks = namespace['blocks']
        t.root_render_func = namespace['root']
        namespace['environment'] = environment
        namespace['__minja_template__'] = t
        return t

    def render(self, *args, **kwargs):
        vars = dict(*args, **kwargs)
        try:
            ctx = self.new_context(vars)
            return concat(self.root_render_func(ctx))
        except Exception:
            raise

    def new_context(self, vars=None):
        return new_context(self.environment, self.name, self.blocks, vars)