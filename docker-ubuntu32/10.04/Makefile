HOST:=http://download.openvz.org/template/precreated
IMAGE:=ubuntu-10.04-x86.tar.gz


image: rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:10.04 .
	docker build -t thekevjames/ubuntu32:lucid .


push: image
	docker push thekevjames/ubuntu32:10.04
	docker push thekevjames/ubuntu32:lucid


rootfs.tar.gz:
	curl -s $(HOST)/$(IMAGE) > $@
