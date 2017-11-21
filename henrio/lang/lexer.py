import ast
import codecs
import re

from ply import lex, yacc

paren_count = 0

ESCAPE_SEQUENCE_RE = re.compile(r'''
    ( \\U........      # 8-digit hex escapes
    | \\u....          # 4-digit hex escapes
    | \\x..            # 2-digit hex escapes
    | \\[0-7]{1,3}     # Octal escapes
    | \\N\{[^}]+\}     # Unicode characters by name
    | \\[\\'"abfnrtv]  # Single-character escapes
    )''', re.UNICODE | re.VERBOSE)


def decode_escapes(s):
    def decode_match(match):
        return codecs.decode(match.group(0), 'unicode-escape')

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)


bracetypes = {
    "{": ast.SetComp,
    "(": ast.GeneratorExp,
    "[": ast.ListComp,
}

binops = {
    "+": ast.Add,
    "-": ast.Sub,
    "*": ast.Mult,
    "/": ast.Div,
    "//": ast.FloorDiv,
    "**": ast.Pow,
    ">>": ast.RShift,
    "<<": ast.LShift,
    "|": ast.BitOr,
    "&": ast.BitAnd,
    "^": ast.BitXor,
    "%": ast.Mod,
    "<": ast.Lt,
    ">": ast.Gt,
    "<=": ast.LtE,
    ">=": ast.GtE,
    "@": ast.MatMult
}

unop = {
    "not": ast.Not,
    "-": ast.USub,
    "+": ast.UAdd,
    "~": ast.Invert,
}

tokens = ('VAR', 'INT', 'FLOAT', 'EQUALS',
          'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
          'LPAREN', 'RPAREN', 'INVERT', 'DOT',
          'FXN', 'RBRACE', 'LBRACE', 'LBRACKET',
          'RBRACKET', 'COMMA', 'AND', 'OR', 'IS',
          'IF', 'ELIF', 'ELSE', 'IMPORT', 'IMPNAME',
          'NEWLINE', 'RETURN', 'STRING', 'TRUE',
          'FALSE', 'POWER', 'COMPLEX', 'DEL', 'AS',
          'FOR', 'IN', 'WHILE', 'BREAK', 'CONTINUE',
          'TAKES', 'CLASS', 'PURE', 'YIELD')

t_EQUALS = r'='
t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_POWER = r'\*\*'
t_INVERT = r'\~'
t_DOT = r'\.'
t_COMMA = r'\,'
t_TAKES = r'<-'
t_PURE = r'\$'

t_ignore = " \t"

reserved = {
    "func": "FXN",
    "if": "IF",
    "else": "ELSE",
    "elif": "ELIF",
    "import": "IMPORT",
    "return": "RETURN",
    "True": "TRUE",
    "False": "FALSE",
    "is": "IS",
    "and": "AND",
    "or": "OR",
    "del": "DEL",
    "as": "AS",
    "for": "FOR",
    "in": "IN",
    "while": "WHILE",
    "break": "BREAK",
    "continue": "CONTINUE",
    "class": "CLASS",
    "yield": "YIELD"
}


def t_VAR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, "VAR")
    return t


def t_IMPNAME(t):
    r'\:[a-zA-Z_][a-zA-Z0-9_]*'
    if t.value[1:] in reserved:
        raise SyntaxError("Bad import name!")
    return t


def t_STRING(t):
    r'b?r?f?\'\'\'[\s\S]*?\'\'\'|b?r?f?\"\"\"[\s\S]*?\"\"\"|b?r?f?\"[^\n\r]*?\"|b?r?f?\'[^\n\r]*?\''
    t.value = ast.parse(t.value).body[0].value
    return t


def t_FLOAT(t):
    r'(\d*\.\d+|\d+\.)j?'
    if t.value.endswith("j"):
        t.value = ast.Num(complex(t.value))
        t.type = 'COMPLEX'
        return t
    t.value = ast.Num(float(t.value))
    return t


def t_INT(t):
    r'\d+j?'
    if t.value.endswith("j"):
        t.value = ast.Num(complex(t.value))
        t.type = 'COMPLEX'
        return t

    t.value = ast.Num(int(t.value))
    return t


def t_comment(t):
    r"[ ]*\043[^\n]*"  # \043 is '#'
    pass


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    t.type = "NEWLINE"
    if paren_count != 0:
        return t


def t_LPAREN(t):
    r"""\("""
    global paren_count
    paren_count += 1
    return t


def t_RPAREN(t):
    r'\)'
    global paren_count
    paren_count -= 1
    return t


def t_LBRACE(t):
    r'\{\n*'
    global paren_count
    paren_count += 1
    return t


def t_RBRACE(t):
    r'\n*\}'
    global paren_count
    paren_count -= 1
    return t


def t_LBRACKET(t):
    r'\['
    global paren_count
    paren_count += 1
    return t


def t_RBRACKET(t):
    r'\]'
    global paren_count
    paren_count -= 1
    return t


def t_error(t):
    raise SyntaxError(f"Illegal char {t.value}")


precedence = (
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS', 'INVERT'),
)


def p_statement_hio_import(p):  # note use importlib loaders?
    '''stmt : IMPORT IMPNAME
            | IMPORT IMPNAME AS VAR'''
    if len(p) == 5:
        alias = p[4]
    else:
        alias = p[2][1:]
    loader = ast.Call(ast.Name("load_hio", ast.Load()), [ast.Str(p[2][1:] + ".hio")], [], lineno=p.lexer.lineno)
    lexpr = ast.Expr(loader, lineno=p.lexer.lineno, col_offset=paren_count)
    importer = ast.Import([ast.alias(p[2][1:], alias)], lineno=p.lexer.lineno)
    p[0] = [lexpr, importer]


def p_statement_import(p):
    '''stmt : IMPORT VAR
            | IMPORT VAR AS VAR'''
    if len(p) == 5:
        alias = p[4]
    else:
        alias = p[2]
    p[0] = ast.Import([ast.alias(p[2], alias)], lineno=p.lexer.lineno)


def p_assign_left(p):
    '''assignment : VAR EQUALS
                  | fargs EQUALS
                  | csa EQUALS
                  | expression DOT VAR EQUALS'''
    if len(p) == 5:
        p[0] = ast.Attribute(p[1], p[3], ast.Store())
    elif isinstance(p[0], str):
        p[0] = ast.Name(id=p[1], ctx=ast.Store())
    else:
        p[0] = ast.Tuple(p[1], ast.Store())


def p_assign_complete(p):
    '''stmt : assignment expression
            | assignment csv'''
    p[0] = Assign(p[1], p[2])


def p_expression_csa(p):
    '''csa : VAR
           | csa COMMA VAR
    '''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]


def p_statement_func_args(p):
    '''fargs : LPAREN csa RPAREN
             | LPAREN csa COMMA RPAREN
             | LPAREN RPAREN
    '''
    if len(p) == 3:
        p[0] = ()
    else:
        p[0] = tuple(p[2])


def p_stmts(p):
    '''stmts : stmt
             | stmts NEWLINE stmt
             | stmts NEWLINE
    '''
    if len(p) == 2:
        p[0] = [p[1]] if type(p[1]) is not list else p[1]
    elif len(p) == 3:
        p[0] = p[1]
    else:
        p[1].append(p[3]) if type(p[3]) is not list else p[1].extend(p[3])
        p[0] = p[1]


def p_return_stmt(p):
    "stmt : RETURN expression"
    p[0] = ast.Return(p[2])


def p_yield_stmt(p):
    """stmt : YIELD expression
            | assignment YIELD expression"""

    p[0] = ast.Yield(p[2])

    if len(p) == 4:
        p[0] = Assign(p[1], p[0])


def p_compound_stmt(p):
    """stmt : if_stmt
            | funcdef
            | classdef"""
    p[0] = p[1]


def p_expr_stmt(p):
    'expr_stmt : expression'
    p[0] = ast.Expr(p[1])


def p_stmt_expr(p):
    'stmt : expr_stmt'
    p[0] = p[1]


def p_if_stmt(p):
    'if_stmt : IF expression body'
    p[0] = ast.If(p[2], p[3], [])


def p_foreach_stmt(p):
    '''stmt : FOR VAR TAKES expression body
            | FOR csa TAKES expression body
            | FOR VAR TAKES expression body ELSE body
            | FOR csa TAKES expression body ELSE body'''
    orelse = []
    if len(p) == 8:
        orelse = p[7]
    if isinstance(p[2], list):
        p[2] = ast.Tuple(p[2], ast.Store())
    else:
        p[2] = ast.Name(p[2], ast.Store())
    p[0] = ast.For(p[2], p[4], p[5], orelse)


def p_for_stmt(p):
    '''stmt : FOR expression body body body
            | FOR expression body body body ELSE body'''
    if len(p) == 8:
        orelse = p[7]
    else:
        orelse = []

    p[5].extend(p[4])
    whilel = ast.While(p[2], p[5], orelse)
    p[3].append(whilel)
    p[0] = whilel


def p_while_stmt(p):
    '''stmt : WHILE expression body
            | WHILE expression body ELSE body'''
    if len(p) == 6:
        orelse = p[5]
    else:
        orelse = []
    p[0] = ast.While(p[2], p[3], orelse)


def p_comprehension(p):
    '''expression : LPAREN expression FOR VAR TAKES expression RPAREN
                  | LBRACE expression FOR VAR TAKES expression RBRACE
                  | LBRACKET expression FOR VAR TAKES expression RBRACKET'''
    name = ast.Name(p[4], ast.Store())
    p[0] = ast.comprehension(p[2], [bracetypes[p[1]](name, p[7])], [], 0)


def p_break_stmt(p):
    'stmt : BREAK'
    p[0] = ast.Break()


def p_continue_stmt(p):
    'stmt : CONTINUE'
    p[0] = ast.Continue()


def p_body_stmts(p):
    '''body : LBRACE stmts RBRACE'''
    if len(p) in (4, 5):
        if type(p[2]) is str:
            if len(p) == 5:
                p[0] = p[3]
            else:
                p[0] = []
        else:
            p[0] = p[2]
    else:
        p[0] = []


def p_body_empty(p):
    '''body : LBRACE RBRACE'''
    p[0] = []


def p_expression_csv(p):
    '''csv : expression
           | csv COMMA expression
    '''
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]


def p_tuple(p):
    '''tuple : LPAREN csv RPAREN
             | LPAREN csv COMMA RPAREN
             | LPAREN RPAREN
    '''
    if len(p) == 3:
        p[0] = ()
    else:
        p[0] = tuple(p[2])


def p_call_expr(p):
    '''expression : expression tuple
                  | PURE expression tuple'''
    if len(p) == 3:
        runner = ast.Name("_hio_interpret_call", ast.Load())
        args = list(p[2])
        args.insert(0, p[1])
        call = ast.Call(runner, args, [])
        p[0] = ast.Await(call)
    else:
        p[0] = ast.Call(p[2], list(p[3]))


def p_funcdef(p):
    '''funcdef : FXN VAR fargs body'''
    if p[2].startswith("__") and p[2].endswith("__"):
        p[0] = ast.FunctionDef(p[2],
                               ast.arguments(args=[ast.arg(arg=x, annotation=None) for x in p[3]], vararg=None,
                                             kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                               p[4],
                               [],
                               None)
    else:
        p[0] = ast.AsyncFunctionDef(p[2],
                                    ast.arguments(args=[ast.arg(arg=x, annotation=None) for x in p[3]], vararg=None,
                                                  kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                                    p[4],
                                    [],
                                    None)


def p_classdef(p):
    'classdef : CLASS VAR tuple body'
    p[0] = ast.ClassDef(p[2], list(p[3]), [], p[4], [])


def p_getattr_expr(p):
    'expression : expression DOT VAR'
    p[0] = ast.Attribute(p[1], p[3], ast.Load())


def p_expression_literals(p):
    '''expression : STRING
                  | INT
                  | FLOAT
                  | COMPLEX
    '''
    p[0] = p[1]


def p_expression_var(p):
    'expression : VAR'
    p[0] = ast.Name(id=p[1], ctx=ast.Load())


def p_tuple_litr(p):
    'expression : tuple'
    p[0] = ast.Tuple(list(p[1]), ast.Load())


def p_expression_set(p):
    '''expression : LBRACE csv RBRACE
                  | LBRACE csv COMMA RBRACE
                  | LBRACE RBRACE
    '''
    if len(p) == 3:
        p[0] = ast.Set((), ast.Store())
    else:
        p[0] = ast.Set(p[2], ast.Store())


def p_expression_list(p):
    '''expression : LBRACKET csv RBRACKET
                  | LBRACKET csv COMMA RBRACKET
                  | LBRACKET RBRACKET
    '''
    if len(p) == 3:
        p[0] = ast.List((), ast.Store())
    else:
        p[0] = ast.List(p[2], ast.Store())


def p_expression_binop(p):
    '''expression : expression PLUS expression
              | expression MINUS expression
              | expression TIMES expression
              | expression DIVIDE expression
              | expression POWER expression'''
    p[0] = ast.BinOp(p[1], binops[p[2]](), p[3])


def p_expression_unop(p):
    '''expression : MINUS expression %prec UMINUS
                  |  INVERT expression'''
    p[0] = unop[p[2]](p[1])


def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]


def p_expression_bool(p):
    'expression : TRUE'
    p[0] = ast.NameConstant(True)


def p_expression_fbool(p):
    'expression : FALSE'
    p[0] = ast.NameConstant(True)


def p_file_input_end(p):
    """file_input_end : file_input"""
    p[0] = p[1]


def p_file_input(p):
    """file_input : file_input NEWLINE
                  | file_input stmt
                  | NEWLINE
                  | stmt"""
    if isinstance(list(p)[-1], str):
        if len(p) == 3:
            p[0] = p[1]
        else:
            p[0] = []
    else:
        if len(p) == 3:
            p[0] = p[1] + [p[2]]
        else:
            p[0] = [p[1]]


def p_error(p):
    if p is not None:
        raise SyntaxError(f"Syntax error at {p.type, p.value, p.lexpos, p.lineno, paren_count}")
    else:
        raise EOFError("Reached end of file! Unclosed brace/bracket/paren?")


def Assign(left, right):
    if isinstance(left, (ast.Name, ast.Attribute)):
        # Single assignment on left
        assignment = ast.Assign([left], right)
        return assignment
    elif isinstance(left, (tuple, list)):
        # List of things - make sure they are Name nodes
        left = ast.Tuple(left) if isinstance(left, tuple) else ast.List(left)
        return ast.Assign(left, right)
    else:
        raise SyntaxError("Can't do that yet")


def prep():
    lex.lex()
    return yacc.yacc(start="file_input_end")
