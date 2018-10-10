import ast, textwrap, re

import astor, jinja2

# with open('test/for-loop.py') as f:
#   text = f.read()

with open(__file__) as f:
  text = f.read()

tree = ast.parse(text)

def raw_source(template_text, node):
  src_text = astor.to_source(node).rstrip()
  src_text = ''.join(src_text.splitlines()) # astor sometimes adds random newlines
  return ' ' * node.col_offset + template_text.format(src_text)
  return template_text.format(src_text)

def node_to_val(node):
  arg_type = type(node).__name__
  if arg_type == 'Call':
    # return node.func.id
    return node.func.attr
  elif arg_type == 'Tuple':
    return ', '.join([node_to_val(elt) for elt in node.elts])
  elif arg_type == 'Str':
    return '"{}"'.format(node.s)
  elif arg_type == 'Compare':
    # 'comparators', 'left', 'lineno', 'ops'
    return raw_source('{}', node).strip()[1:-1]
  elif arg_type == 'Name':
    return node.id
  else:
    print "unknown node in node_to_val: {}".format(arg_type)
    return ''

class Walker:
  def __init__(self):
    self.prev_lineno = 0

  def render_template(self, template_text, node, **kw):
    should_indent = kw.get('should_indent', False)

    body_str = self.walk_list(node.body)
    template_text = template_text[1:] # remove initial newline
    template_text = textwrap.dedent(template_text)
    if should_indent:
      template_text = '\n'.join(' ' * node.col_offset + line for line in template_text.splitlines())
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
    print 'ast_type:', ast_type
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
      return self.render_template(
        '''
        {{node.iter.id}}.forEach(function({{node.target.id}}) {
          {{body_str}}
        })
        ''',
        node
      )
    elif ast_type == 'Print':
      # dest, nl, values
      vals = [node_to_val(child) for child in node.values]
      return ' ' * node.col_offset + 'console.log({})'.format(vals)
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

      return self.render_template(
        '''
        function {{node.name}}({{args_str}}) {
        {{body_str}}
        }
        ''',
        node, args_str=args_str
      )
    elif ast_type == 'If':
      return self.handle_if(node, should_indent=True)
    elif ast_type == 'Return':
      src = raw_source('{}', node)
      return src
    elif ast_type == 'list':
      return ''
    else:
      print "unknown node:", ast_type
      return ''

  def handle_if(self, node, should_indent):
    # 'body', 'col_offset', 'lineno', 'orelse', 'test'
    test = node_to_val(node.test)
    if node.orelse and type(node.orelse[0]).__name__ == 'If':
      trailing_str = self.handle_if(node.orelse[0], should_indent=False)
      trailing_str = re.sub('if', 'else if', trailing_str, 1)
    else:
      else_str = self.walk_list(node.orelse)
      trailing_str = self.render_template(
        '''
        else {
          {{else_str}}
        }
        ''',
        node, else_str=else_str
      )
    if_str = self.render_template(
      '''
      if({{test}}) {
        {{body_str}}
      }
      {{trailing_str}}
      ''',
      node, test=test, trailing_str=trailing_str, should_indent=should_indent
    )
    return if_str

js_out = Walker().walk_node(tree)
with open('out.js', 'w') as f:
  f.write(js_out)
