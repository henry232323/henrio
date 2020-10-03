# henrio
A small set of projects I've been working on. The goal is to recreate some major frameworks in Python from scratch. Right now this means an async framework (like asyncio) and an embeddable Python-family language.

Two Parts:
  1. An Async Library modeled after others, with lots of inspiration from Curio, Trio, and AsyncIO.
  It includes many of the same concepts and can interface with multio easily, but doesn't yet have any support for anyio (prs welcome!)
      - 3 Types of Loops: Base Loop with no Async-IO; Selector Loop using the Selector Module; and on Windows,
      the IOCP Loop (Selector is the default)
      - Futures, Tasks, and Conditionals. Wait for a Future to be set, wrap a coroutine, 
      wait for a condition to become true.
      - I/O. Specific operations for avoiding blocking when interacting with raw sockets.
      - File Wrappers: Selector and IOCP Loops provide special wrapped files for interacting with file I/O
      - Queue: A native LIFO/FIFO queue and a Heap Queue; Technically both work with any async lib.
      - Protocols: Selector Only. Modeled after AsyncIO's own protocols, same type of thing but with async callbacks
      - Workers: Using multiprocessing process and thread pools, run sync and async functions in separate threads
      - Loop Methods or Library Functions. Any operation available as a loop method can also be accessed using 
      functions found in the `henrio.yields` module. These will run the associated operation on the Loop processing
      the coroutine. Generally only one loop will be running a coroutine.
      - Universals: `henrio.universals` This is a module containing all classes that can be used between 
      Async libraries. For more information on interoperation see [async-recipes](https://github.com/henry232323/async-recipes)

  2. The Language. Sometimes the parsing actually works, realistically this isn't meant to be used and was more 
  of an attempt to learn about parsing, specifically Lex-Yacc style interpretation. The language has one primary
  feature: all functions are run asynchronously, meaning all function definitions are async and have implicit 
  awaits around every call (turning sync funcs into async funcs) and any top level async calls are run using
  `henrio.run`. Whats included
      - A custom import hook for importing .hio files from Python. First parsing then loading
      - A specially built "compiler" / pyc generator. An attempt at recreating how Python handles compiled 
      files. 
      - Cool other stuff maybe??
      - parser is actually broken rn
  