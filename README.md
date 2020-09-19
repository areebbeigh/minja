# minja
#### ~[ Work in progress ]~ 

A basic (and heavily jinja inspired) python template engine intended to teach myself basic compiler design.

```python
from minja import Template

template = '''{{hello}}
{% if 1 < 2 %}
    <b>{{hello2}}</b>
    {{func('bye')}}
    heya
{% endif %}
{% with x, y = (1, 'test') %}
    {{x}}
{% endwith %}
{% block test %}
    {% for i in get_list() %}
        {{i}}
    {% endfor %}
{% endblock %}
'''

def f():
    return [1,2,3,4]

t = Template(template, autoescape=True)
print(
    t.render(
        hello="Hey there!",
        hello2="<h1>Sup? I'm escaped</h1>",
        get_list=f,
        func=lambda x: x))
```
Output:
```html
Hey there!

    &lt;h1&gt;Sup? I&#39;m escaped&lt;/h1&gt;
    <b>bye</b>
    heya


    1


    
        1
    
        2
    
        3
    
        4
```
