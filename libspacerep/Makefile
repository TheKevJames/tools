.PHONY: clean lib tests
LIBC = build/spacerep.h
LIBCFFI = libspacerep.c

tests: lib venv/bin/activate
	@. venv/bin/activate; PYTHONPATH=$(shell pwd) ./tests/run.py
lib: $(LIBCFFI)

$(LIBC): src/*.nim
	nimble make

$(LIBCFFI): $(LIBC) venv/bin/activate
	. venv/bin/activate; ./ffibuild.py

venv/bin/activate: tests/requirements.txt
	python3 -m venv venv
	. venv/bin/activate; pip install -r $<

clean:
	rm -rf build/
	rm -rf venv/
	rm -f libspacerep.*
