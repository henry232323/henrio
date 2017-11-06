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
          'IF', 'ELIF', 'ELSE', 'IMPORT', #'COLON',
          'NEWLINE', 'RETURN', 'STRING', 'TRUE',
          'FALSE', 'POWER', 'COMPLEX', 'DEL', 'AS')

t_EQUALS = r'='
t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_POWER = r'\*\*'
t_INVERT = r'\~'
t_DOT = r'\.'
t_FXN = r'func'
t_COMMA = r'\,'
#t_COLON = r'\:'

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
    "as": "AS"
}


def t_VAR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, "VAR")
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


def p_statement_import(p):
    '''stmt : IMPORT VAR
            | IMPORT VAR AS VAR'''
    if len(p) == 5:
        alias = p[4]
    else:
        alias = p[2]
    p[0] = ast.Import([ast.alias(p[2], alias)], lineno=p.lexer.lineno)


def p_statement_assign(p):
    'stmt : VAR EQUALS expression'
    name = ast.Name(id=p[1], ctx=ast.Store())
    p[0] = Assign(name, p[3])


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
             | stmts NEWLINE'''
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 3:
        p[0] = p[1]
    else:
        p[1].append(p[3])
        p[0] = p[1]


def p_return_stmt(p):
    "stmt : RETURN expression"
    p[0] = ast.Return(p[2])


def p_compound_stmt(p):
    """stmt : if_stmt
            | funcdef"""
    p[0] = p[1]


def p_expr_stmt(p):
    'stmt : expression'
    p[0] = ast.Expr(p[1])


def p_if_stmt(p):
    'if_stmt : IF expression body'
    p[0] = ast.If([(p[2], p[4])], None)


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
    'expression : expression tuple'
    p[0] = ast.Call(p[1], list(p[2]), [])


def p_funcdef(p):
    '''funcdef : FXN VAR fargs body'''
    p[0] = ast.AsyncFunctionDef(p[2],
                                ast.arguments(args=[ast.arg(arg=x, annotation=None) for x in p[3]], vararg=None,
                                              kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                                p[4],
                                [],
                                None)


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
    p[0] = binops[p[2]](left=p[1], right=p[3])


def p_expression_unop(p):
    '''expression : MINUS expression %prec UMINUS
                  |  INVERT expression'''
    p[0] = unop[p[2]](p[1])


def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]


def p_expression_bool(p):
    'expression : TRUE'
    p[0] = True


def p_expression_fbool(p):
    'expression : FALSE'
    p[0] = False


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
    if isinstance(left, ast.Name):
        # Single assignment on left
        assignment = ast.Assign([left], right)
        return assignment
    elif isinstance(left, (ast.Tuple, ast.List)):
        # List of things - make sure they are Name nodes
        return ast.Assign(left, right)
    else:
        raise SyntaxError("Can't do that yet")


def prep():
    lex.lex()
    return yacc.yacc(start="file_input_end")
