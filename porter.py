import ast, textwrap

import jinja2

with open('for-loop.py') as f:
  text = f.read()

tree = ast.parse(text)

def walk(node):
  ast_type = type(node).__name__
  if ast_type == 'Module':
    for child in node.body:
      return walk(child)
  elif ast_type == 'For':
    text = textwrap.dedent(
      '''
      {{node.iter.id}}.forEach(function({{node.target.id}}) {
        {{body_str}}
      })
      '''
    )

    child_strs = [walk(child) for child in node.body]
    body_str = '\n'.join(child_strs)
    js_text = jinja2.Template(text).render(node=node, body_str=body_str)
    return js_text
  elif ast_type == 'Print':
    return 'console.log({})'.format(node.values[0].id)
  else:
    print "unknown node:", ast_type
    return ''

print walk(tree)

