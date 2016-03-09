HOST:=https://partner-images.canonical.com/core
IMAGE:=xenial/current/ubuntu-xenial-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:16.04 .
	docker build -t thekevjames/ubuntu32:xenial .
	docker build -t thekevjames/ubuntu32:latest .


push: image
	docker push thekevjames/ubuntu32:16.04
	docker push thekevjames/ubuntu32:xenial
	docker push thekevjames/ubuntu32:latest


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
