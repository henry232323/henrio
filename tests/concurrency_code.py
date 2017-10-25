from threading import Thread


def printers():
    my_strings = ["Hello!", "How", "are", "you?"]
    for string in my_strings:
        Thread(target=print, args=(string,)).start()


printers()


def printers2():
    my_strings = ["How", "you?", "Hello!", "are"]
    for string in my_strings:
        Thread(target=print, args=(string,)).start()


printers2()
