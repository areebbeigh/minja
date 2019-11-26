from lexer import Lexer
from parser import Parser
from compiler import generate
from environment import Template

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
template = '''
{{hello}}
{% block content %}
    {{test()}}
    {{d['t']}}
    {{obj.x}}
    {{hello}}
    {% with x = 100 %}
        {{func(x, 1)}}
    {% endwith %}
    {% block test %}
        {{hello, func(2)}}
        {{func(1)}}
        {% if hello %}
            {{hello_}}
            hey there!
        {% endif %}
        {% block test2 %}
            {{func(hello)}}
            {% with x = 2 %}
                {{func(x)}}
            {% endwith %}
        {% endblock %}
        {% for i in items %}{{i}}{% endfor %}
        {% if 1 == 0 %}yes{% endif %}
    {% endblock %}
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
t = Template(template)
print(t.render(items=[1,2,3,4]))
