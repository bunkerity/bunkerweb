FROM golang:1.20-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the source files to the container
COPY ./bw-data/plugins/coraza/confs/ /app

RUN apk add git wget tar 

RUN go install github.com/corazawaf/coraza-access

RUN go mod tidy 

# Start the binary when the container starts
CMD ["go", "run", "/app/."]
