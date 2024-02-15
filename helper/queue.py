from _thread import allocate_lock
import xbmc

class Queue:
    def __init__(self):
        self.Lock = allocate_lock()
        self.QueuedItems = ()
        self.Lock.acquire()
        self.Busy = False

    def get(self):
        with self.Lock:
            self.Busy = True
            ReturnData = self.QueuedItems[0]
            self.QueuedItems = self.QueuedItems[1:]

        if not self.QueuedItems:
            self.LockQueue()

        self.Busy = False
        return ReturnData

    def getall(self):
        try:
            with self.Lock:
                self.Busy = True
                ReturnData = self.QueuedItems
                self.QueuedItems = ()
        except Exception as Error:
            xbmc.log(f"EMBY.helper.queue: getall: {Error}", 2) # LOGWARNING

        self.LockQueue()
        self.Busy = False
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
        if not self.Lock.locked():
            self.Lock.acquire()

    def UnLockQueue(self):
        while self.Busy:
            xbmc.sleep(1)

        if self.Lock.locked():
            self.Lock.release()

    def clear(self):
        self.Busy = True
        self.LockQueue()
        self.QueuedItems = ()
        self.Busy = False

    def isEmpty(self):
        return not bool(self.QueuedItems)
