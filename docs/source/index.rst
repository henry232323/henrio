.. henrio documentation master file, created by
   sphinx-quickstart on Mon Dec 25 22:11:42 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to henrio's documentation!
==================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   
Abstract Bases
-----------------

.. autoclass:: henrio.AbstractLoop
   :members:
   
.. autoclass:: henrio.BaseFile
   :members:
   :undoc-members:
   
.. autoclass:: henrio.BaseSocket
   :members:
   :undoc-members:
   
.. autoclass:: henrio.IOBase
   :members:
   :undoc-members:
   
   
Futures & Tasks
-------------------

.. autoclass:: henrio.Future
   :members:
   
.. autoclass:: henrio.Task
   :members:
   
.. autoclass:: henrio.Conditional
   :members:
   
.. autoclass:: henrio.Event
   :members:

.. autoclass:: henrio.timeout
   :members:
   
   
Locks
-------

.. autoclass:: henrio.Lock
   :members:
   :undoc-members:
   
.. autoclass:: henrio.ResourceLock
   :members:
   :undoc-members:
   
.. autoclass:: henrio.Semaphore
   :members:
   :undoc-members:
   
   
Loops
-------

.. autoclass:: henrio.BaseLoop
   :members:
   :undoc-members:
   

.. autoclass:: henrio.SelectorLoop
   :members:
   :undoc-members:
   

.. autoclass:: henrio.IOCPLoop
   :members:
   :undoc-members:
   
.. autoclass:: henrio.IOCPFile
   :members:
   :undoc-members:


I/O
-------
.. autoclass:: henrio.AsyncSocket
    :members:

.. autoclass:: henrio.AsyncFile
    :members:

.. automodule:: henrio.io
   :members:
   :special-members:
   :undoc-members:


Queues
---------

.. autoclass:: henrio.Queue
   :members:
   :undoc-members:
   
.. autoclass:: henrio.HeapQueue
   :members:
   :undoc-members:
   
.. autoexception:: henrio.QueueWouldBlock
   :members:
   :undoc-members:
   
   
Workers
----------

.. automodule:: henrio.workers
   :members:
   :private-members:
   :special-members:
   :undoc-members:
   
   
Special Yields
----------------

.. automodule:: henrio.yields
   :members:
   :private-members:
   :special-members:
   :undoc-members:
   

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
