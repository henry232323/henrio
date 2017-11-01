import ast
from traceback import print_exc

from ply import lex, yacc

tokens = ('VAR', 'INT', 'FLOAT', 'EQUALS',
          'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
          'LPAREN', 'RPAREN', 'INVERT', 'DOT',
          'FXN', 'RBRACE', 'LBRACE', 'LBRACKET',
          'RBRACKET', 'COMMA', 'INDENT', 'COLON',
          'WS')

t_EQUALS = r'='
t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_INVERT = r'~'
t_DOT = r'.'
t_FXN = r'func'
t_COMMA = r'\,'
t_INDENT = r'\s\s\s\s'
t_COLON = r'\:'

t_ignore = " \t"

reserved = {
    "func": "FXN",
    "if": "IF",
    "else": "ELSE",
    "elif": "ELIF"
}


def t_VAR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, "VAR")
    return t


def t_FLOAT(t):
    r'(\d*\.\d+|\d+\.)'
    t.value = float(t.value)
    return t


def t_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    print(f"Illegal char {t.value}")
    t.lexer.skip(1)


names = dict()

precedence = (
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS', 'INVERT'),
    # ('right' 'fargs', 'tuple')
)


def p_statement_assign(p):
    'statement : VAR EQUALS expression'
    names[p[1]] = p[3]


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


def p_expression_name(p):
    'expression : VAR'
    try:
        p[0] = names[p[1]]
    except LookupError:
        raise NameError(f"name '{p[1]}' is not defined!") from None


def p_exp_fargs(p):
    'expression : FXN fargs'
    p[0] = p[2]


def p_statement_expr(p):
    'statement : expression'
    print(p[1])


def p_body_stmts(p):
    'body : LBRACE RBRACE'


def p_statement_func(p):
    'statement : FXN VAR fargs body'
    names[p[2]] = ast.AsyncFunctionDef(p[2], tuple(p[3]), p[4], (), None)


def p_getattr_expr(p):
    'expression : expression DOT VAR'
    p[0] = getattr(p[1], p[3])


def p_call_expr(p):
    'expression : expression tuple'
    p[0] = p[1](p[2])


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


def p_expression_tuple(p):
    '''expression : tuple'''
    p[0] = p[1]


def p_expression_set(p):
    '''expression : LBRACE csv RBRACE
                    | LBRACE csv COMMA RBRACE
                    | LBRACE RBRACE
    '''
    if len(p) == 3:
        p[0] = set()
    else:
        p[0] = set(p[2])


def p_expression_list(p):
    '''expression : LBRACKET csv RBRACKET
                    | LBRACKET csv COMMA RBRACKET
                    | LBRACKET RBRACE
    '''
    if len(p) == 3:
        p[0] = list()
    else:
        p[0] = p[2]


def p_expression_binop(p):
    '''expression : expression PLUS expression
              | expression MINUS expression
              | expression TIMES expression
              | expression DIVIDE expression'''
    if p[2] == '+':
        p[0] = p[1] + p[3]
    elif p[2] == '-':
        p[0] = p[1] - p[3]
    elif p[2] == '*':
        p[0] = p[1] * p[3]
    elif p[2] == '/':
        p[0] = p[1] / p[3]


def p_expression_number(p):
    '''expression : INT
             | FLOAT'''
    p[0] = p[1]


def p_expression_unop(p):
    '''expression : MINUS expression %prec UMINUS
              |  INVERT expression'''
    if p[1] == "~":
        p[0] = ~p[2]
    elif p[1] == "-":
        p[0] = -p[2]


def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]


def p_error(p):
    print(f"Syntax error at {p.value if p else None}")


def prep():
    lex.lex()
    yacc.yacc()
