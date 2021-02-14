SCONS := scons-2.7

.PHONY: all
all: \
    memcached \
    mutilate

.PHONY: clean
clean: \
    clean-memcached \
    clean-mutilate

.PHONY: memcached
memcached:
	cd ./memcached \
	    && (test -e ./configure || ./autogen.sh) \
	    && (test -e ./Makefile || ./configure) \
	    && $(MAKE)

.PHONY: clean-memcached
clean-memcached:
	cd ./memcached \
	    && $(MAKE) clean

.PHONY: mutilate
mutilate:
	cd ./mutilate \
	    && $(SCONS)

.PHONY: clean-mutilate
clean-mutilate:
	cd ./mutilate \
	    && $(SCONS) -c
