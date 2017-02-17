HOST:=https://partner-images.canonical.com/core
IMAGE:=yakkety/current/ubuntu-yakkety-core-cloudimg-i386-root.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:16.10 .
	docker build -t thekevjames/ubuntu32:yakkety .
	docker build -t thekevjames/ubuntu32:latest .


push: image
	docker push thekevjames/ubuntu32:16.10
	docker push thekevjames/ubuntu32:yakkety
	docker push thekevjames/ubuntu32:latest


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
