from lexer import Lexer
from parser import Parser
from compiler import generate

class E:
    autoescape = True
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
{% with x, y = (1, 'test') %}
    {{x}}
{% endwith %}
{% block test %}
    {% for i in func() %}
        {{i}}
    {% endfor %}
{% endblock %}'''

template = '''
{{hello}}
{% block content %}
{% for i in items %}
    {{i}}
{% else %}
    heya
{% endfor %}
{% endblock %}
'''

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

ast = p.parse()
print(ast)
s = generate(ast, e, 'test')
with open('output.py', 'w') as f:
    f.write(s)
