.PHONY: all publish publish-force Cargo.lock
all: README.md Cargo.lock
publish: README.md Cargo.lock
	cargo publish
publish-force: README.md Cargo.lock
	cargo publish --allow-dirty

README.md: README.rst
	pandoc -t gfm $^ > $@

Cargo.lock: Cargo.toml
	cargo update
