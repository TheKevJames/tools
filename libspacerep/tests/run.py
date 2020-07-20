#!/usr/bin/env python3
from libspacerep import lib


if __name__ == '__main__':
    for i in range(1, 30):
        print(f'fib({i}) = {lib.fib(i)}')
