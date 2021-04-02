CMAKE := cmake
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
	lighttpd \
	mysql \
	redis \
	memtier

.PHONY: clean clean-all
clean clean-all: \
	clean-memcached \
	clean-mutilate \
	clean-nginx \
	clean-ppd \
	clean-rocksdb \
	clean-bcpi \
	clean-lighttpd \
	clean-mysql \
	clean-redis \
	clean-memtier

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

.PHONY: mysql
mysql:
	mkdir -p ./mysql-server/build \
	    && cd ./mysql-server/build \
	    && $(CMAKE) .. \
	        -DBUILD_CONFIG=mysql_release \
	        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
	        -DDOWNLOAD_BOOST=1 \
	        -DWITH_BOOST=boost \
	    && $(MAKE)

.PHONY: clean-mysql
clean-mysql:
	rm -rf ./mysql-server/build

.PHONY: redis
redis:
	cd ./redis && \
		$(GMAKE)

.PHONY: clean-redis
clean-redis:
	cd ./redis && \
		$(GMAKE) distclean

.PHONY: memtier
memtier:
	cd ./memtier && \
		autoreconf -ivf && \
		./configure && \
		$(GMAKE)

.PHONY: clean-memtier
clean-memtier:
	cd ./memtier && \
		$(GMAKE) clean
