class TemplateError(Exception):
    """Base class for all template errors"""
    def __init__(self, message=None):
        Exception.__init__(self, message)
    
    @property
    def message(self):
        if self.args:
            message = self.args[0]
            if message is not None:
                return message


class TemplateSyntaxError(TemplateError):
    def __init__(self, message, lineno, name=None, filename=None):
        TemplateError.__init__(self, message)
        self.lineno = lineno
        self.name = name
        self.filename = filename
        
    def __str__(self):
        location = 'line %d' % self.lineno
        name = self.filename or self.name
        if name:
            location = 'File "%s", %s' % (name, location)
        lines = [self.message, '  ' + location]
        return u'\n'.join(lines)


class TemplateRuntimeError(TemplateError):
    """A generic runtime error in the template engine."""


class UndefinedError(TemplateRuntimeError):
    """Raised if a template tries to operator on :class:`Undefined`."""