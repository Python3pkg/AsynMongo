#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############
# Date    : 2016-03-08 10:32:06
# Author  : Victor Lin
# Email    : linxianwusx@gmail.com
###############
from Queue import Queue

class PythonQueue(Queue):
    def __init__(self, name, maxsize = 0):
        Queue.__init__(self, name)
        self.get_len = 0
        self.put_len = 0
        self.name = name

    def put_left(self,item):
        self.queue.appendleft(item)
        self.put_len += 1

    def _put(self, item):
        self.queue.append(item)
        self.put_len += 1

    def _get(self):
        return self.queue.popleft()
        self.get_len += 1

    def clear(self):
        self.queue.clear()
        return True

    def key(self):
        return self.name