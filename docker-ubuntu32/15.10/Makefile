HOST:=https://partner-images.canonical.com/core
IMAGE:=wily/current/ubuntu-wily-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:15.10 .
	docker build -t thekevjames/ubuntu32:wily .


push: image
	docker push thekevjames/ubuntu32:15.10
	docker push thekevjames/ubuntu32:wily


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
