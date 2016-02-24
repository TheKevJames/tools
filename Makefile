SUBDIRS := $(wildcard */.)
.PHONY: $(SUBDIRS)


all: $(SUBDIRS)


$(SUBDIRS):
	make -C $@ image
