import lexer
from ply import yacc

lexer.prep()

while True:
    try:
        s = input('>>> ')
    except EOFError:
        break
    yacc.parse(s)
