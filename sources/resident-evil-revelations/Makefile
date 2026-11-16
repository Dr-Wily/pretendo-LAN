.PHONY: build run tidy vet clean

build:
	CGO_ENABLED=0 go build -o build/rerev-nex .

run: build
	./build/rerev-nex

tidy:
	go mod tidy

vet:
	go vet ./...

clean:
	rm -rf build log
