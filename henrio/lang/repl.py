from traceback import print_exc

from .compiler import eval


def run_repl():
    while True:
        try:
            s = input('>>> ')
            if s.endswith("{"):
                while not s.endswith("}"):
                    s += "\n"
                    s += input('... ')

            print(eval(s, globals(), locals()))
        except (EOFError, KeyboardInterrupt):
            break
        except:
            print_exc()
