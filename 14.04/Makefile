HOST:=https://partner-images.canonical.com/core
IMAGE:=trusty/current/ubuntu-trusty-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:14.04 .
	docker build -t thekevjames/ubuntu32:trusty .


push: image
	docker push thekevjames/ubuntu32:14.04
	docker push thekevjames/ubuntu32:trusty


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
