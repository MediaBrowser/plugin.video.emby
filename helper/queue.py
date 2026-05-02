import collections
import threading

class Queue:
    def __init__(self):
        self.ItemsQueue = collections.deque()
        self.ThreadCondition = threading.Condition(threading.Lock())

    def put(self, data):
        with self.ThreadCondition:
            if isinstance(data, (list, tuple)):
                self.ItemsQueue.extend(data)
            else:
                self.ItemsQueue.append(data)
            self.ThreadCondition.notify_all()

    def get(self):
        while True:
            with self.ThreadCondition:
                if self.ItemsQueue:
                    return self.ItemsQueue.popleft()

                self.ThreadCondition.wait(timeout=0.1)

    def getall(self):
        while True:
            with self.ThreadCondition:
                if self.ItemsQueue:
                    items = list(self.ItemsQueue)
                    self.ItemsQueue.clear()
                    self.ThreadCondition.notify_all()
                    return items

                self.ThreadCondition.wait(timeout=0.1)

    def clear(self):
        with self.ThreadCondition:
            self.ItemsQueue.clear()
            self.ThreadCondition.notify_all()

    def isEmpty(self):
        with self.ThreadCondition:
            return not self.ItemsQueue
