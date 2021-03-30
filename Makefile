GMAKE := gmake
SCONS := scons
SCONS2 := scons-2.7

.PHONY: all
all: \
	memcached \
	mutilate \
	nginx \
	rocksdb \
	ppd \
	bcpi \
	lighttpd

.PHONY: clean clean-all
clean clean-all: \
	clean-memcached \
	clean-mutilate \
	clean-nginx \
	clean-ppd \
	clean-rocksdb \
	clean-bcpi \
	clean-lighttpd

.PHONY: memcached
memcached:
	cd ./memcached \
	    && (test -e ./configure || ./autogen.sh) \
	    && (test -e ./Makefile || ./configure) \
	    && $(MAKE)

.PHONY: clean-memcached
clean-memcached:
	cd ./memcached

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
	cd ./nginx

.PHONY: rocksdb
rocksdb:
	cd ./rocksdb \
		&& $(GMAKE) static_lib -j48 \
		&& sudo $(GMAKE) install

.PHONY: clean-rocksdb
clean-rocksdb:
	cd ./rocksdb \
		&& $(GMAKE) clean

.PHONY: ppd
ppd:
	cd ./kqsched/pingpong \
		&& mkdir -p build \
		&& cd build \
		&& cmake .. \
		&& $(MAKE)

.PHONY: clean-ppd
clean-ppd:
	rm -rf ./kqsched/pingpong/build

.PHONY: bcpi
bcpi:
	cd ./bcpi \
	&& make

.PHONY: clean-bcpi
clean-bcpi:
	cd ./bcpi \
	&& make clean

.PHONY: lighttpd
lighttpd:
	cd ./lighttpd \
	    && $(SCONS) build_static=1 build_dynamic=0

.PHONY: clean-lighttpd
clean-lighttpd:
	cd ./lighttpd \
	    && $(SCONS) -c