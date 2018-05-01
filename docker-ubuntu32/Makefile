all: 10.04 12.04 14.04 14.10 15.04 15.10 16.04 16.10 17.04 17.10 18.04

push:
	docker push thekevjames/ubuntu32
	docker push thekevjames/ubuntu32:latest


release/%/Dockerfile: Dockerfile.template
	cp $< $@

release/10.04/rootfs.tar.gz:
	curl -s "http://download.openvz.org/template/precreated/unsupported/ubuntu-10.04-x86.tar.gz" > $@

release/12.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/precise/current/ubuntu-precise-core-cloudimg-i386-root.tar.gz" > $@

release/14.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/trusty/current/ubuntu-trusty-core-cloudimg-i386-root.tar.gz" > $@

release/14.10/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/utopic/current/ubuntu-utopic-core-cloudimg-i386-root.tar.gz" > $@

release/15.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/vivid/current/ubuntu-vivid-core-cloudimg-i386-root.tar.gz" > $@

release/15.10/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/wily/current/ubuntu-wily-core-cloudimg-i386-root.tar.gz" > $@

release/16.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/xenial/current/ubuntu-xenial-core-cloudimg-i386-root.tar.gz" > $@

release/16.10/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/yakkety/current/ubuntu-yakkety-core-cloudimg-i386-root.tar.gz" > $@

release/17.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/unsupported/zesty/current/ubuntu-zesty-core-cloudimg-i386-root.tar.gz" > $@

release/17.10/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/artful/current/ubuntu-artful-core-cloudimg-i386-root.tar.gz" > $@

release/18.04/rootfs.tar.gz:
	curl -s "https://partner-images.canonical.com/core/bionic/current/ubuntu-bionic-core-cloudimg-i386-root.tar.gz" > $@

release/%:
	mkdir -p $@

clean:
	rm -rf release

10.04: release/10.04 release/10.04/Dockerfile release/10.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:10.04 release/10.04/
	docker build -t thekevjames/ubuntu32:lucid release/10.04/

12.04: release/12.04 release/12.04/Dockerfile release/12.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:12.04 release/12.04/
	docker build -t thekevjames/ubuntu32:precise release/12.04/

14.04: release/14.04 release/14.04/Dockerfile release/14.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:14.04 release/14.04/
	docker build -t thekevjames/ubuntu32:trusty release/14.04/

14.10: release/14.10 release/14.10/Dockerfile release/14.10/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:14.10 release/14.10/
	docker build -t thekevjames/ubuntu32:utopic release/14.10/

15.04: release/15.04 release/15.04/Dockerfile release/15.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:15.04 release/15.04/
	docker build -t thekevjames/ubuntu32:vivid release/15.04/

15.10: release/15.10 release/15.10/Dockerfile release/15.10/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:15.10 release/15.10/
	docker build -t thekevjames/ubuntu32:wily release/15.10/

16.04: release/16.04 release/16.04/Dockerfile release/16.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:16.04 release/16.04/
	docker build -t thekevjames/ubuntu32:xenial release/16.04/

16.10: release/16.10 release/16.10/Dockerfile release/16.10/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:16.10 release/16.10/
	docker build -t thekevjames/ubuntu32:yakkety release/16.10/

17.04: release/17.04 release/17.04/Dockerfile release/17.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:17.04 release/17.04/
	docker build -t thekevjames/ubuntu32:zesty release/17.04/

17.10: release/17.10 release/17.10/Dockerfile release/17.10/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:17.10 release/17.10/
	docker build -t thekevjames/ubuntu32:artful release/17.10/

18.04: release/18.04 release/18.04/Dockerfile release/18.04/rootfs.tar.gz
	docker build -t thekevjames/ubuntu32:18.04 release/18.04/
	docker build -t thekevjames/ubuntu32:bionic release/18.04/
	docker build -t thekevjames/ubuntu32:latest release/18.04/
