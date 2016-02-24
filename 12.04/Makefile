HOST:=https://partner-images.canonical.com/core
IMAGE:=precise/current/ubuntu-precise-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:12.04 .
	docker build -t thekevjames/ubuntu32:precise .


push: image
	docker push thekevjames/ubuntu32:12.04
	docker push thekevjames/ubuntu32:precise


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
