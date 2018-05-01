HOST:=https://partner-images.canonical.com/core
IMAGE:=vivid/current/ubuntu-vivid-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:15.04 .
	docker build -t thekevjames/ubuntu32:vivid .


push: image
	docker push thekevjames/ubuntu32:15.04
	docker push thekevjames/ubuntu32:vivid


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
