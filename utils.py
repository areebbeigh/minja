from markupsafe import Markup, escape

concat = u''.join

class MissingType:
    def __repr__(self):
        return 'missing'

missing = MissingType()
