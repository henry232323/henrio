try:
    import lexer
except ImportError:
    from . import lexer
from traceback import print_exc

from ply import yacc

lexer.prep()

while True:
    try:
        s = input('>>> ')
        if s.endswith("{"):
            while not s.endswith("}"):
                s += "\n"
                s += input('... ')

            yacc.parse(s)
        else:
            yacc.parse(s)
    except (EOFError, KeyboardInterrupt):
        break
    except:
        print_exc()
