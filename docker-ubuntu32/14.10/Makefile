HOST:=https://partner-images.canonical.com/core
IMAGE:=utopic/current/ubuntu-utopic-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:14.10 .
	docker build -t thekevjames/ubuntu32:utopic .


push: image
	docker push thekevjames/ubuntu32:14.10
	docker push thekevjames/ubuntu32:utopic


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
