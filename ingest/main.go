// ingress is the Go stage for the polyglot pipeline defined in
// docs/adrs/adr-011-polyglot-architecture.md (rev 4).
//
// Responsibility: verify the BODMAS zip SHA-256, control the unzip into a
// controlled RW derived area, SHA-256 every file, join metadata by sha256, and
// write the manifest + sample table.
//
// This file is a scaffold. It compiles as a placeholder until G0 work starts.
package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stdout, "ingest: scaffold placeholder")
}
