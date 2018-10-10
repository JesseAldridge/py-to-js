import ast, textwrap

import astor, jinja2

# with open('test/for-loop.py') as f:
#   text = f.read()

with open(__file__) as f:
  text = f.read()

tree = ast.parse(text)

def raw_source(template_text, node):
  return ' ' * node.col_offset + template_text.format(astor.to_source(node))

class Walker:
  def __init__(self):
    self.prev_lineno = 0

  def render(self, template_text, node, **kw):
    body_str = self.walk_list(node.body)
    template_text = template_text[1:] # remove initial newline
    template_text = textwrap.dedent(template_text)
    js_str = jinja2.Template(template_text).render(node=node, body_str=body_str, **kw)
    # return textwrap.dedent(js_str)
    return js_str

  def walk_node(self, node):
    blank_line = False
    if hasattr(node, 'lineno'):
      if node.lineno - self.prev_lineno > 1:
        blank_line = True

    out_str = self._walk_node(node, self.prev_lineno)
    if blank_line:
      out_str = '\n' + out_str
    return out_str

  def walk_list(self, children):
    child_strs = [self.walk_node(child) for child in children]
    return '\n'.join(child_strs)

  def _walk_node(self, node, prev_lineno):
    if hasattr(node, 'lineno'):
      self.prev_lineno = node.lineno
    ast_type = type(node).__name__
    if ast_type == 'Module':
      return self.walk_list(node.body)
    elif ast_type == 'Import':
      names = [name.name for name in node.names]
      lines = ['require("{}")'.format(name) for name in names]
      return '\n'.join(lines)
    elif ast_type == 'alias':
      # asname, name
      return node.name
    elif ast_type == 'For':
      return self.render(
        '''
        {{node.iter.id}}.forEach(function({{node.target.id}}) {
          {{body_str}}
        })
        ''',
        node
      )
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
        args = node.context_expr.args
        filename_arg = args[0]
        is_write = (len(args) == 2 and hasattr(args[1], 's') and args[1].s == 'w')
        if is_write:
          function_name = 'writeFileSync'
          assignment_expr = ''
        else:
          function_name = 'readFileSync'
          assignment_expr = 'let {} = '.format(node.body[0].targets[0].id)

        # Assign vs Expr
        if hasattr(filename_arg, 'id'):
          filename = filename_arg.id
          if filename == '__file__':
            filename = '__filename'
        else:
          filename = '"{}"'.format(filename_arg.s)
        return '{}fs.{}({})'.format(assignment_expr, function_name, filename)
      else:
        pass
    elif ast_type == 'Assign':
      # targets, value
      return raw_source('let {}', node)
    elif ast_type == 'FunctionDef':
      # 'args', 'body', 'col_offset', 'decorator_list', 'lineno', 'name'
      args_str = ', '.join([arg.id for arg in node.args.args])

      return self.render(
        '''
        function {{node.name}}({{args_str}}) {
        {{body_str}}
        }
        ''',
        node, args_str=args_str
      )
    elif ast_type == 'Return':
      return raw_source('{}', node)
    else:
      print "unknown node:", ast_type
      return ''

js_out = Walker().walk_node(tree)
with open('out.js', 'w') as f:
  f.write(js_out)
