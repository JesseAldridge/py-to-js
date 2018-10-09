import ast, textwrap

import astor, jinja2

# with open('test/for-loop.py') as f:
#   text = f.read()

with open(__file__) as f:
  text = f.read()

tree = ast.parse(text)

def walk_list(children):
  child_strs = [walk_node(child) for child in children]
  return '\n'.join(child_strs)

def walk_node(node):
  ast_type = type(node).__name__
  if ast_type == 'Module':
    return walk_list(node.body)
  elif ast_type == 'Import':
    # return walk_list(node.names)
    return ''
  elif ast_type == 'alias':
    # asname, name
    return node.name
  elif ast_type == 'For':
    text = textwrap.dedent(
      '''
      {{node.iter.id}}.forEach(function({{node.target.id}}) {
        {{body_str}}
      })
      '''
    )

    body_str = walk_list(node.body)
    js_text = jinja2.Template(text).render(node=node, body_str=body_str)
    return js_text
  elif ast_type == 'Print':
    # dest, nl, values
    if type(node.values[0]).__name__ == 'Call':
      val_str = node.values[0].func.id
    else:
      val_str = node.values[0].id
    return 'console.log({})'.format(val_str)
  elif ast_type == 'With':
    # 'body', 'col_offset', 'context_expr', 'lineno', 'optional_vars'
    # context_expr: _ast.Call, 'args', 'col_offset', 'func', 'keywords', 'kwargs', 'lineno', 'starargs'
    # func: _ast.Name

    if node.context_expr.func.id == 'open':
      arg = node.context_expr.args[0]
      if hasattr(arg, 'id'):
        filename = arg.id
        if filename == '__file__':
          filename = '__filename'
      else:
        filename = '"{}"'.format(arg.s)
      return 'fs.readFileSync({})'.format(filename)
    else:
      pass
  elif ast_type == 'Assign':
    # targets, value
    return 'let ' + astor.to_source(node)
  else:
    print "unknown node:", ast_type
    return ''

js_out = walk_node(tree)
with open('out.js', 'w') as f:
  f.write(js_out)

