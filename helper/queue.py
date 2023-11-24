from _thread import allocate_lock


class Queue:
    def __init__(self):
        self.Lock = allocate_lock()
        self.QueuedItems = ()
        self.Locked = True
        self.Lock.acquire()

    def get(self):
        with self.Lock:
            ReturnData = self.QueuedItems[0]
            self.QueuedItems = self.QueuedItems[1:]

        if not self.QueuedItems:
            self.LockQueue()

        return ReturnData

    def getall(self):
        with self.Lock:
            ReturnData = self.QueuedItems
            self.QueuedItems = ()

        self.LockQueue()
        return ReturnData

    def put(self, Data):
        if isinstance(Data, list):
            self.QueuedItems += tuple(Data)
        elif isinstance(Data, tuple):
            self.QueuedItems += Data
        else:
            self.QueuedItems += (Data,)

        self.UnLockQueue()

    def LockQueue(self):
        if not self.Locked:
            self.Locked = True
            self.Lock.acquire()

    def UnLockQueue(self):
        if self.Locked:
            self.Locked = False
            self.Lock.release()

    def clear(self):
        self.LockQueue()
        self.QueuedItems = ()

    def isEmpty(self):
        return bool(self.QueuedItems)
