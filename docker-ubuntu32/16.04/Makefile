HOST:=https://partner-images.canonical.com/core
IMAGE:=xenial/current/ubuntu-xenial-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:16.04 .
	docker build -t thekevjames/ubuntu32:xenial .


push: image
	docker push thekevjames/ubuntu32:16.04
	docker push thekevjames/ubuntu32:xenial


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
