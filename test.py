from lexer import Lexer
from parser import Parser

class E:
    def tokenize(self, source):
        l = Lexer(None)
        return l.tokenize(source)
        
template = '''
{{hello}}
{% if 1 < 2 %}
    {{hello2}}
    {{func()}}
    heya
{% endif %}
{% with x, y = (1, 2) %}
    {{x}}
{% endwith %}
{% block test %}
    {% for i in func() %}
        {{i}}
    {% endfor %}
{% endblock %}'''

e = E()
l = Lexer(None)
# stream = l.tokenize(template)
# for i in range(10):
#     print(next(stream), stream.closed)
p = Parser(e, template)

# stream = (l.tokenize(template))

# for l in stream:
#     print(l)

# print(next(stream))

print(p.parse())
