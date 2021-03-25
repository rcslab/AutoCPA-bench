GMAKE := gmake
SCONS := scons
SCONS2 := scons-2.7

.PHONY: all
all: \
    memcached \
    mutilate \
    nginx

.PHONY: clean
clean: \
    clean-memcached \
    clean-mutilate \
    clean-nginx

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
	    && $(SCONS2)

.PHONY: clean-mutilate
clean-mutilate:
	cd ./mutilate \
	    && $(SCONS2) -c

.PHONY: nginx
nginx:
	cd ./nginx \
	    && (test -e ./Makefile || ./auto/configure) \
	    && $(MAKE)

.PHONY: clean-nginx
clean-nginx:
	cd ./nginx \
	    && $(MAKE) clean

.PHONY: lighttpd
lighttpd:
	cd ./lighttpd \
	    && $(SCONS) build_static=1 build_dynamic=0

.PHONY: clean-lighttpd
clean-lighttpd:
	cd ./lighttpd \
	    && $(SCONS) -c
